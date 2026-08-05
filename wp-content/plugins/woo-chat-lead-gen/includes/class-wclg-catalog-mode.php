<?php
/**
 * Modalità catalogo: WooCommerce senza carrello, checkout e pagamenti.
 *
 * Il blocco è server-side (non solo estetico): anche una chiamata diretta a
 * `?add-to-cart=123` o all'endpoint AJAX viene rifiutata.
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Catalog_Mode {

	/**
	 * @var WCLG_Catalog_Mode|null
	 */
	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Flusso attivo: 'cart' oppure 'direct'.
	 *
	 * @var string
	 */
	private $flow;

	private function __construct() {
		$this->flow = WCLG_Settings::get( 'order_flow', 'cart' );

		if ( 'cart' === $this->flow ) {
			// Il carrello serve: si disattiva solo la parte transazionale.
			add_action( 'template_redirect', array( $this, 'redirect_checkout' ) );
			$this->disable_payments();
		} elseif ( WCLG_Settings::is( 'disable_cart' ) ) {
			$this->disable_cart();
			$this->disable_payments();
		}

		if ( WCLG_Settings::is( 'hide_price' ) ) {
			add_filter( 'woocommerce_get_price_html', '__return_empty_string', 99 );
		}

		add_filter( 'body_class', array( $this, 'body_class' ) );
	}

	/**
	 * Nel flusso carrello il checkout non esiste: si torna al riepilogo.
	 */
	public function redirect_checkout() {
		if ( is_admin() || wp_doing_ajax() || ! function_exists( 'is_checkout' ) ) {
			return;
		}
		// La pagina "ordine ricevuto" resta raggiungibile: è solo una conferma.
		if ( ! is_checkout() || is_order_received_page() ) {
			return;
		}

		wp_safe_redirect( wc_get_cart_url(), 302 );
		exit;
	}

	/* --------------------------------------------------------------------- *
	 * Carrello
	 * --------------------------------------------------------------------- */

	private function disable_cart() {
		// 1. Rifiuta ogni aggiunta al carrello (form, link diretto, AJAX, blocchi).
		add_filter( 'woocommerce_add_to_cart_validation', array( $this, 'block_add_to_cart' ), 99, 3 );

		// 2. Pagine carrello/checkout non raggiungibili.
		add_action( 'template_redirect', array( $this, 'redirect_cart_pages' ) );

		// 3. Nessun mini-carrello nei widget/menu del tema.
		add_filter( 'woocommerce_widget_cart_is_hidden', '__return_true', 99 );

		// 4. L'add-to-cart AJAX degli archivi non ha più senso: via le classi.
		add_filter( 'woocommerce_loop_add_to_cart_args', array( $this, 'strip_ajax_class' ), 99 );
	}

	/**
	 * Blocca l'aggiunta al carrello.
	 *
	 * @param bool $passed     Esito della validazione.
	 * @param int  $product_id ID prodotto.
	 * @param int  $quantity   Quantità.
	 * @return bool Sempre false.
	 */
	public function block_add_to_cart( $passed, $product_id = 0, $quantity = 0 ) {
		if ( ! is_admin() && function_exists( 'wc_add_notice' ) ) {
			wc_add_notice(
				esc_html__( 'Gli ordini si concludono in chat: usa il pulsante di contatto nella scheda prodotto.', 'woo-chat-lead-gen' ),
				'notice'
			);
		}
		return false;
	}

	/**
	 * Carrello e checkout reindirizzano allo shop.
	 */
	public function redirect_cart_pages() {
		if ( is_admin() || wp_doing_ajax() ) {
			return;
		}
		if ( ! function_exists( 'is_cart' ) || ! ( is_cart() || is_checkout() ) ) {
			return;
		}

		$destination = wc_get_page_permalink( 'shop' );
		/**
		 * Filtra la destinazione del redirect da carrello/checkout.
		 *
		 * @param string $destination URL di destinazione.
		 */
		$destination = apply_filters( 'wclg_cart_redirect_url', $destination ? $destination : home_url( '/' ) );

		wp_safe_redirect( $destination, 302 );
		exit;
	}

	/**
	 * Rimuove le classi AJAX dal pulsante di archivio (sostituito dal CTA chat).
	 *
	 * @param array $args Argomenti del link add-to-cart.
	 * @return array
	 */
	public function strip_ajax_class( $args ) {
		if ( isset( $args['class'] ) ) {
			$args['class'] = trim( str_replace( array( 'ajax_add_to_cart', 'add_to_cart_button' ), '', $args['class'] ) );
		}
		return $args;
	}

	/* --------------------------------------------------------------------- *
	 * Pagamenti
	 * --------------------------------------------------------------------- */

	private function disable_payments() {
		// Nessun gateway disponibile: il checkout non è completabile in alcun modo.
		add_filter( 'woocommerce_available_payment_gateways', '__return_empty_array', 99 );
		add_filter( 'woocommerce_cart_needs_payment', '__return_false', 99 );
		add_filter( 'woocommerce_order_needs_payment', '__return_false', 99 );
		// Nasconde la sezione Pagamenti nella pagina impostazioni? No: l'admin resta intatto.
	}

	/* --------------------------------------------------------------------- *
	 * Utility
	 * --------------------------------------------------------------------- */

	/**
	 * @param array $classes Classi del body.
	 * @return array
	 */
	public function body_class( $classes ) {
		$classes[] = 'wclg-catalog-mode';
		$classes[] = 'wclg-flow-' . $this->flow;
		if ( 'direct' === $this->flow && WCLG_Settings::is( 'sticky_mobile' ) ) {
			$classes[] = 'wclg-has-sticky-cta';
		}
		return $classes;
	}
}
