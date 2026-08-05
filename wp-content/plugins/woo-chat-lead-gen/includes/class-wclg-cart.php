<?php
/**
 * Carrello orientato alla chat.
 *
 * Il carrello resta quello nativo di WooCommerce (righe, quantità, varianti),
 * ma perde il pulsante "Procedi all'ordine" a favore dell'invio in chat, e
 * guadagna una stima di spedizione e un totale dichiarato come stimato.
 *
 * Espone anche i dati del carrello in forma normalizzata: è la sorgente unica
 * per il riepilogo a schermo, il drawer e il messaggio WhatsApp.
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Cart {

	/**
	 * @var WCLG_Cart|null
	 */
	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		// Pagina carrello: via il checkout, dentro il CTA chat.
		remove_action( 'woocommerce_proceed_to_checkout', 'woocommerce_button_proceed_to_checkout', 20 );
		add_action( 'woocommerce_proceed_to_checkout', array( $this, 'render_cart_cta' ), 20 );

		// Riepilogo totali: spedizione stimata + totale stimato.
		add_action( 'woocommerce_cart_totals_before_order_total', array( $this, 'render_shipping_row' ) );
		add_filter( 'woocommerce_cart_totals_order_total_html', array( $this, 'order_total_html' ) );

		// Il calcolatore di spedizione nativo confonde: la stima è la nostra.
		if ( 'woo' !== WCLG_Settings::get( 'shipping_mode' ) ) {
			add_filter( 'woocommerce_cart_ready_to_calc_shipping', '__return_false', 99 );
			add_filter( 'woocommerce_cart_needs_shipping', '__return_false', 99 );
		}

		// Pagina più pulita.
		remove_action( 'woocommerce_cart_collaterals', 'woocommerce_cross_sell_display' );

		// Mini carrello / drawer.
		remove_action( 'woocommerce_widget_shopping_cart_buttons', 'woocommerce_widget_shopping_cart_button_view_cart', 10 );
		remove_action( 'woocommerce_widget_shopping_cart_buttons', 'woocommerce_widget_shopping_cart_proceed_to_checkout', 20 );
		add_action( 'woocommerce_widget_shopping_cart_buttons', array( $this, 'render_mini_cart_buttons' ), 20 );
		add_action( 'woocommerce_widget_shopping_cart_before_buttons', array( $this, 'render_mini_cart_estimate' ), 20 );

		if ( WCLG_Settings::is( 'cart_drawer' ) ) {
			add_action( 'wp_footer', array( $this, 'render_drawer' ) );
			add_filter( 'woocommerce_add_to_cart_fragments', array( $this, 'cart_fragments' ) );
		}

		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue_assets' ), 20 );
	}

	/**
	 * Il drawer vive in ogni pagina, quindi gli asset servono ovunque.
	 *
	 * Lo stile è già registrato da WCLG_Frontend: qui lo si accoda soltanto.
	 */
	public function enqueue_assets() {
		if ( is_admin() ) {
			return;
		}

		if ( wp_style_is( 'wclg-frontend', 'registered' ) ) {
			wp_enqueue_style( 'wclg-frontend' );
		}

		if ( WCLG_Settings::is( 'cart_drawer' ) ) {
			wp_enqueue_script( 'wclg-cart', WCLG_URL . 'assets/js/wclg-cart.js', array( 'jquery' ), WCLG_VERSION, true );
			// Serve per l'aggiornamento automatico del mini carrello.
			wp_enqueue_script( 'wc-cart-fragments' );
		}
	}

	/* --------------------------------------------------------------------- *
	 * Dati normalizzati del carrello
	 * --------------------------------------------------------------------- */

	/**
	 * Righe del carrello in forma piatta.
	 *
	 * @return array<int,array{name:string,variant:string,qty:int,sku:string,total:float,price_label:string,on_request:bool}>
	 */
	public static function get_items() {
		if ( ! function_exists( 'WC' ) || ! WC()->cart ) {
			return array();
		}

		$items = array();

		foreach ( WC()->cart->get_cart() as $cart_item ) {
			$product = isset( $cart_item['data'] ) ? $cart_item['data'] : null;
			if ( ! $product instanceof WC_Product ) {
				continue;
			}

			$on_request = WCLG_Price::is_on_request( $product );
			$total      = (float) ( $cart_item['line_subtotal'] ?? 0 ) + (float) ( $cart_item['line_subtotal_tax'] ?? 0 );

			$items[] = array(
				'name'        => self::item_name( $product ),
				'variant'     => self::item_variant( $product ),
				'qty'         => (int) $cart_item['quantity'],
				'sku'         => (string) $product->get_sku(),
				'total'       => $on_request ? 0.0 : $total,
				'price_label' => $on_request
					? WCLG_Price::label()
					: WCLG_Message::plain_text( wc_price( $total ) ),
				'on_request'  => $on_request,
			);
		}

		/**
		 * Filtra le righe normalizzate del carrello.
		 *
		 * @param array $items Righe.
		 */
		return apply_filters( 'wclg_cart_items', $items );
	}

	/**
	 * Nome del prodotto padre, senza gli attributi appesi dalle variazioni.
	 *
	 * @param WC_Product $product Prodotto o variazione.
	 * @return string
	 */
	private static function item_name( $product ) {
		$id = $product->is_type( 'variation' ) ? $product->get_parent_id() : $product->get_id();
		return html_entity_decode( wp_strip_all_tags( get_the_title( $id ) ), ENT_QUOTES, 'UTF-8' );
	}

	/**
	 * Valori degli attributi scelti: "M" oppure "M, Nero".
	 *
	 * @param WC_Product $product Prodotto o variazione.
	 * @return string
	 */
	private static function item_variant( $product ) {
		if ( ! $product->is_type( 'variation' ) ) {
			return '';
		}
		return WCLG_Message::plain_text( wc_get_formatted_variation( $product, true, false ) );
	}

	/**
	 * Totali del carrello, spedizione inclusa.
	 *
	 * @return array{count:int,subtotal:float,subtotal_label:string,shipping:array,total:float,total_label:string,has_on_request:bool}
	 */
	public static function get_totals() {
		$items    = self::get_items();
		$shipping = WCLG_Shipping::estimate();

		$subtotal       = 0.0;
		$count          = 0;
		$has_on_request = false;

		foreach ( $items as $item ) {
			$subtotal += $item['total'];
			$count    += $item['qty'];
			$has_on_request = $has_on_request || $item['on_request'];
		}

		$total = $subtotal + ( $shipping['on_request'] ? 0.0 : (float) $shipping['amount'] );
		$label = WCLG_Message::plain_text( wc_price( $total ) );

		// Se qualcosa non ha prezzo, il totale è dichiaratamente parziale.
		if ( $has_on_request || $shipping['on_request'] ) {
			$label .= ' ' . __( '(+ voci da concordare)', 'woo-chat-lead-gen' );
		}

		return array(
			'count'          => $count,
			'subtotal'       => $subtotal,
			'subtotal_label' => WCLG_Message::plain_text( wc_price( $subtotal ) ),
			'shipping'       => $shipping,
			'total'          => $total,
			'total_label'    => $label,
			'has_on_request' => $has_on_request,
		);
	}

	/**
	 * Impronta del carrello: cambia solo se cambia il contenuto.
	 *
	 * Serve a riusare lo stesso numero d'ordine se l'utente riapre la chat
	 * senza aver toccato il carrello.
	 *
	 * @return string
	 */
	public static function get_hash() {
		$signature = array();
		foreach ( self::get_items() as $item ) {
			$signature[] = $item['name'] . '|' . $item['variant'] . '|' . $item['qty'] . '|' . $item['total'];
		}
		return md5( implode( ';', $signature ) );
	}

	/* --------------------------------------------------------------------- *
	 * Pagina carrello
	 * --------------------------------------------------------------------- */

	/**
	 * Riga "Spedizione stimata" nella tabella totali.
	 */
	public function render_shipping_row() {
		$shipping = WCLG_Shipping::estimate();
		?>
		<tr class="wclg-shipping-row">
			<th><?php esc_html_e( 'Spedizione stimata', 'woo-chat-lead-gen' ); ?></th>
			<td data-title="<?php esc_attr_e( 'Spedizione stimata', 'woo-chat-lead-gen' ); ?>">
				<span class="wclg-shipping-row__value"><?php echo esc_html( $shipping['label'] ); ?></span>
				<small class="wclg-shipping-row__note"><?php echo esc_html( WCLG_Shipping::describe() ); ?></small>
			</td>
		</tr>
		<?php
	}

	/**
	 * Sostituisce il totale nativo con quello stimato (spedizione inclusa).
	 *
	 * @param string $html Totale originale.
	 * @return string
	 */
	public function order_total_html( $html ) {
		$totals = self::get_totals();

		return sprintf(
			'<strong class="wclg-total">%s</strong><small class="wclg-total__note">%s</small>',
			esc_html( $totals['total_label'] ),
			esc_html__( 'Totale stimato, confermato in chat', 'woo-chat-lead-gen' )
		);
	}

	/**
	 * CTA principale della pagina carrello.
	 */
	public function render_cart_cta() {
		echo $this->get_cta_html(); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- markup sanificato in get_cta_html().
	}

	/**
	 * Markup del pulsante "Invia ordine su WhatsApp".
	 *
	 * @param string $context cart|drawer.
	 * @return string
	 */
	public function get_cta_html( $context = 'cart' ) {
		$url = WCLG_Order::get_chat_url();
		if ( '' === $url ) {
			return '';
		}

		return sprintf(
			'<a href="%1$s" class="button alt wclg-button wclg-button--order wclg-button--%2$s" data-wclg-order-cta rel="nofollow"%3$s>%4$s<span>%5$s</span></a>',
			esc_url( $url ),
			esc_attr( $context ),
			WCLG_Settings::is( 'new_tab' ) ? ' target="_blank"' : '',
			$this->get_icon(),
			esc_html( WCLG_Settings::get( 'cart_button_label' ) )
		);
	}

	/**
	 * @return string Icona del canale attivo.
	 */
	private function get_icon() {
		return '<svg class="wclg-button__icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.87 9.87 0 004.74 1.21h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0012.04 2z"/></svg>';
	}

	/* --------------------------------------------------------------------- *
	 * Mini carrello e drawer
	 * --------------------------------------------------------------------- */

	/**
	 * Stima spedizione + totale dentro il mini carrello.
	 */
	public function render_mini_cart_estimate() {
		$totals = self::get_totals();
		?>
		<div class="wclg-mini-totals">
			<div class="wclg-mini-totals__row">
				<span><?php esc_html_e( 'Spedizione stimata', 'woo-chat-lead-gen' ); ?></span>
				<span><?php echo esc_html( $totals['shipping']['label'] ); ?></span>
			</div>
			<div class="wclg-mini-totals__row wclg-mini-totals__row--total">
				<span><?php esc_html_e( 'Totale stimato', 'woo-chat-lead-gen' ); ?></span>
				<span><?php echo esc_html( $totals['total_label'] ); ?></span>
			</div>
		</div>
		<?php
	}

	/**
	 * Pulsanti del mini carrello: vedi carrello + invia ordine.
	 */
	public function render_mini_cart_buttons() {
		printf(
			'<a href="%1$s" class="button wclg-button--ghost">%2$s</a>',
			esc_url( wc_get_cart_url() ),
			esc_html__( 'Vedi carrello', 'woo-chat-lead-gen' )
		);
		echo $this->get_cta_html( 'drawer' ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
	}

	/**
	 * Drawer laterale + pulsante flottante con contatore.
	 */
	public function render_drawer() {
		if ( is_admin() || ( function_exists( 'is_cart' ) && is_cart() ) ) {
			return;
		}
		$totals = self::get_totals();
		?>
		<button type="button" class="wclg-fab" data-wclg-drawer-open aria-controls="wclg-drawer"
			aria-label="<?php esc_attr_e( 'Apri il carrello', 'woo-chat-lead-gen' ); ?>">
			<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
				<path fill="currentColor" d="M7 4h-.75A1.25 1.25 0 005 5.25v.5C5 6.44 5.56 7 6.25 7H7l1.6 8.6A2 2 0 0010.57 17h6.86a2 2 0 001.97-1.64L21 8H8m1.5 12a1 1 0 11-2 0 1 1 0 012 0m10 0a1 1 0 11-2 0 1 1 0 012 0"/>
			</svg>
			<span class="wclg-fab__count" data-wclg-count><?php echo esc_html( $totals['count'] ); ?></span>
		</button>

		<div class="wclg-drawer" id="wclg-drawer" data-wclg-drawer hidden>
			<div class="wclg-drawer__backdrop" data-wclg-drawer-close></div>
			<aside class="wclg-drawer__panel" role="dialog" aria-modal="true"
				aria-label="<?php esc_attr_e( 'Il tuo ordine', 'woo-chat-lead-gen' ); ?>">
				<header class="wclg-drawer__head">
					<h2 class="wclg-drawer__title"><?php esc_html_e( 'Il tuo ordine', 'woo-chat-lead-gen' ); ?></h2>
					<button type="button" class="wclg-drawer__close" data-wclg-drawer-close
						aria-label="<?php esc_attr_e( 'Chiudi', 'woo-chat-lead-gen' ); ?>">&times;</button>
				</header>
				<div class="wclg-drawer__body widget_shopping_cart_content">
					<?php woocommerce_mini_cart(); ?>
				</div>
			</aside>
		</div>
		<?php
	}

	/**
	 * Tiene aggiornato il contatore del FAB dopo un add-to-cart AJAX.
	 *
	 * Il contenuto del drawer usa `div.widget_shopping_cart_content`, che
	 * WooCommerce aggiorna già da sé.
	 *
	 * @param array $fragments Frammenti.
	 * @return array
	 */
	public function cart_fragments( $fragments ) {
		$totals = self::get_totals();

		$fragments['[data-wclg-count]'] = sprintf(
			'<span class="wclg-fab__count" data-wclg-count>%s</span>',
			esc_html( $totals['count'] )
		);

		return $fragments;
	}
}
