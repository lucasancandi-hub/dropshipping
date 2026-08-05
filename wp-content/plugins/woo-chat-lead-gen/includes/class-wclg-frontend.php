<?php
/**
 * Frontend: rimozione dei pulsanti nativi e rendering del CTA chat.
 *
 * Strategia per la scheda prodotto:
 *  - prodotti semplici/esterni: si rimuove del tutto il template add-to-cart;
 *  - prodotti variabili/raggruppati: si mantiene il form (serve il selettore
 *    taglia) e si "ingoia" via output buffering solo quantità + bottone.
 * In entrambi i casi il CTA chat viene stampato subito dopo.
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Frontend {

	/**
	 * @var WCLG_Frontend|null
	 */
	private static $instance = null;

	/**
	 * Livello di output buffering aperto (0 = nessuno).
	 *
	 * @var int
	 */
	private $buffer_level = 0;

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

		add_action( 'wp_enqueue_scripts', array( $this, 'register_assets' ) );
		add_shortcode( 'wclg_chat_button', array( $this, 'shortcode' ) );

		if ( 'cart' === $this->flow ) {
			// I pulsanti nativi restano: il carrello è parte del flusso.
			// Sotto al form mettiamo solo un link discreto per le domande.
			if ( WCLG_Settings::is( 'single_chat_link' ) ) {
				add_action( 'woocommerce_after_add_to_cart_form', array( $this, 'render_inline_chat_link' ), 20 );
			}
			return;
		}

		add_action( 'wp', array( $this, 'setup_single_product' ) );

		// Archivio / griglia prodotti.
		add_filter( 'woocommerce_loop_add_to_cart_link', array( $this, 'loop_button' ), 99, 2 );

		// Barra CTA fissa su mobile.
		if ( WCLG_Settings::is( 'sticky_mobile' ) ) {
			add_action( 'wp_footer', array( $this, 'render_sticky_bar' ) );
		}
	}

	/**
	 * Link testuale alla chat sotto il pulsante "Aggiungi al carrello".
	 *
	 * Nel flusso carrello la conversione principale è l'aggiunta al carrello:
	 * la chat resta disponibile per dubbi su taglie e disponibilità.
	 */
	public function render_inline_chat_link() {
		global $product;
		if ( ! $product instanceof WC_Product ) {
			return;
		}

		$url = WCLG_Message::product_url( $product );
		if ( '' === $url ) {
			return;
		}

		printf(
			'<p class="wclg-inline-chat"><a href="%1$s" rel="nofollow"%2$s>%3$s</a></p>',
			esc_url( $url ),
			WCLG_Settings::is( 'new_tab' ) ? ' target="_blank"' : '',
			esc_html__( 'Dubbi sulla taglia o sulla disponibilità? Scrivici su WhatsApp', 'woo-chat-lead-gen' )
		);
	}

	/* --------------------------------------------------------------------- *
	 * Asset
	 * --------------------------------------------------------------------- */

	public function register_assets() {
		if ( WCLG_Settings::is( 'load_css' ) ) {
			wp_register_style( 'wclg-frontend', WCLG_URL . 'assets/css/wclg-frontend.css', array(), WCLG_VERSION );
		}
		wp_register_script( 'wclg-frontend', WCLG_URL . 'assets/js/wclg-frontend.js', array( 'jquery' ), WCLG_VERSION, true );

		if ( $this->is_woocommerce_context() ) {
			$this->enqueue_assets();
		}
	}

	/**
	 * Accoda gli asset (idempotente: usato anche dallo shortcode).
	 */
	public function enqueue_assets() {
		if ( WCLG_Settings::is( 'load_css' ) ) {
			wp_enqueue_style( 'wclg-frontend' );
		}
		wp_enqueue_script( 'wclg-frontend' );
	}

	/**
	 * @return bool
	 */
	private function is_woocommerce_context() {
		return function_exists( 'is_woocommerce' ) && ( is_woocommerce() || is_product() || is_shop() || is_product_taxonomy() );
	}

	/* --------------------------------------------------------------------- *
	 * Scheda prodotto
	 * --------------------------------------------------------------------- */

	/**
	 * Registra gli hook giusti in base al tipo di prodotto.
	 */
	public function setup_single_product() {
		if ( ! function_exists( 'is_product' ) || ! is_product() ) {
			return;
		}

		$product = wc_get_product( get_queried_object_id() );
		if ( ! $product instanceof WC_Product ) {
			return;
		}

		if ( $product->is_type( array( 'variable', 'grouped' ) ) ) {
			// Il form resta (serve per scegliere la taglia): togliamo quantità e bottone.
			add_action( 'woocommerce_before_add_to_cart_button', array( $this, 'start_buffer' ), -9999 );
			add_action( 'woocommerce_after_add_to_cart_button', array( $this, 'discard_buffer' ), 9999 );
			// Rete di sicurezza se un tema sovrascrive il template e salta gli hook.
			add_action( 'woocommerce_after_add_to_cart_form', array( $this, 'flush_buffer' ), 1 );
			add_action( 'woocommerce_after_single_product_summary', array( $this, 'flush_buffer' ), -9999 );
			add_action( 'shutdown', array( $this, 'flush_buffer' ), 0 );

			add_action( 'woocommerce_after_add_to_cart_form', array( $this, 'render_single_cta' ), 5 );
		} else {
			remove_action( 'woocommerce_single_product_summary', 'woocommerce_template_single_add_to_cart', 30 );
			add_action( 'woocommerce_single_product_summary', array( $this, 'render_single_cta' ), 30 );
		}
	}

	public function start_buffer() {
		if ( $this->buffer_level ) {
			return;
		}
		ob_start();
		$this->buffer_level = ob_get_level();
	}

	/**
	 * Chiude il buffer scartandone il contenuto (quantità + bottone nativo).
	 */
	public function discard_buffer() {
		if ( $this->buffer_level && ob_get_level() >= $this->buffer_level ) {
			ob_end_clean();
		}
		$this->buffer_level = 0;
	}

	/**
	 * Chiude il buffer stampandone il contenuto: usato solo come fallback,
	 * per non perdere output se il template del tema non chiama i nostri hook.
	 */
	public function flush_buffer() {
		if ( $this->buffer_level && ob_get_level() >= $this->buffer_level ) {
			ob_end_flush();
		}
		$this->buffer_level = 0;
	}

	/**
	 * Stampa il CTA nella scheda prodotto.
	 */
	public function render_single_cta() {
		global $product;
		if ( ! $product instanceof WC_Product ) {
			$product = wc_get_product( get_queried_object_id() );
		}
		if ( $product instanceof WC_Product ) {
			echo $this->get_button_html( $product, array( 'context' => 'single' ) ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- markup già sanificato in get_button_html().
		}
	}

	/* --------------------------------------------------------------------- *
	 * Archivio
	 * --------------------------------------------------------------------- */

	/**
	 * Sostituisce il link "Aggiungi al carrello" della griglia.
	 *
	 * @param string     $html    Markup originale.
	 * @param WC_Product $product Prodotto.
	 * @return string
	 */
	public function loop_button( $html, $product ) {
		if ( ! $product instanceof WC_Product ) {
			return $html;
		}

		$label = WCLG_Settings::get( 'loop_button_label' );

		// Sui prodotti con varianti conviene passare dalla scheda: lì si sceglie la taglia.
		if ( 'product' === WCLG_Settings::get( 'loop_button_action' ) || $product->is_type( 'variable' ) ) {
			return sprintf(
				'<a href="%1$s" class="button wclg-button wclg-button--loop" data-wclg-context="loop">%2$s</a>',
				esc_url( $product->get_permalink() ),
				esc_html( $label )
			);
		}

		return $this->get_button_html(
			$product,
			array(
				'context' => 'loop',
				'label'   => $label,
				'wrapper' => false,
			)
		);
	}

	/* --------------------------------------------------------------------- *
	 * Markup del pulsante
	 * --------------------------------------------------------------------- */

	/**
	 * Costruisce il markup completo del CTA.
	 *
	 * @param WC_Product $product Prodotto.
	 * @param array      $args    context|label|wrapper|quantity.
	 * @return string
	 */
	public function get_button_html( $product, $args = array() ) {
		$args = wp_parse_args(
			$args,
			array(
				'context'  => 'single',
				'label'    => WCLG_Settings::get( 'button_label' ),
				'wrapper'  => true,
				'quantity' => WCLG_Settings::is( 'show_quantity' ) && 'single' === ( $args['context'] ?? 'single' ),
			)
		);

		$url = WCLG_Message::product_url( $product );
		if ( '' === $url ) {
			return '';
		}

		$label = $product->is_in_stock()
			? $args['label']
			: __( 'Chiedi disponibilità', 'woo-chat-lead-gen' );

		/**
		 * Filtra l'etichetta del pulsante.
		 *
		 * @param string     $label   Etichetta.
		 * @param WC_Product $product Prodotto.
		 * @param string     $context single|loop|shortcode.
		 */
		$label = apply_filters( 'wclg_button_label', $label, $product, $args['context'] );

		$target = WCLG_Settings::is( 'new_tab' ) ? ' target="_blank" rel="noopener nofollow"' : ' rel="nofollow"';

		$button = sprintf(
			'<a href="%1$s" class="button wclg-button wclg-button--%2$s" data-wclg-action="chat" data-wclg-context="%2$s"%3$s>%4$s%5$s</a>',
			esc_url( $url ),
			esc_attr( $args['context'] ),
			$target,
			$this->get_icon(),
			esc_html( $label )
		);

		if ( ! $args['wrapper'] ) {
			return $button;
		}

		$quantity = $args['quantity'] ? $this->get_quantity_field( $product ) : '';

		return sprintf(
			'<div class="wclg-cta" data-wclg="%1$s">%2$s%3$s%4$s</div>',
			esc_attr( wp_json_encode( $this->get_js_payload( $product ) ) ),
			$quantity,
			$button,
			$this->get_reassurance()
		);
	}

	/**
	 * Dati necessari al JS per ricostruire il link quando cambia la variante.
	 *
	 * @param WC_Product $product Prodotto.
	 * @return array
	 */
	private function get_js_payload( $product ) {
		$vars = WCLG_Message::build_vars( $product );

		return array(
			'prefix'      => $this->get_url_prefix(),
			'template'    => WCLG_Settings::get( 'message_template' ),
			'vars'        => $vars,
			'hidePrice'   => WCLG_Settings::is( 'hide_price' ),
			'priceFormat' => array(
				'symbol'      => html_entity_decode( get_woocommerce_currency_symbol(), ENT_QUOTES, 'UTF-8' ),
				'decimals'    => wc_get_price_decimals(),
				'decimalSep'  => wc_get_price_decimal_separator(),
				'thousandSep' => wc_get_price_thousand_separator(),
				'format'      => get_woocommerce_price_format(),
			),
		);
	}

	/**
	 * Parte fissa dell'URL, fino a `text=` incluso: il JS accoda solo il
	 * messaggio codificato, così la logica di canale resta in PHP.
	 *
	 * @return string
	 */
	private function get_url_prefix() {
		$url = WCLG_Message::build_url( '' );
		return '' === $url ? '' : $url;
	}

	/**
	 * Campo quantità (indipendente dal carrello: serve solo al messaggio).
	 *
	 * @param WC_Product $product Prodotto.
	 * @return string
	 */
	private function get_quantity_field( $product ) {
		return sprintf(
			'<div class="wclg-qty"><label class="screen-reader-text" for="wclg-qty-%1$d">%2$s</label>
			<button type="button" class="wclg-qty__btn" data-wclg-step="-1" aria-label="%3$s">&minus;</button>
			<input type="number" id="wclg-qty-%1$d" class="wclg-qty__input" value="1" min="1" step="1" inputmode="numeric">
			<button type="button" class="wclg-qty__btn" data-wclg-step="1" aria-label="%4$s">+</button></div>',
			(int) $product->get_id(),
			esc_html__( 'Quantità', 'woo-chat-lead-gen' ),
			esc_attr__( 'Diminuisci quantità', 'woo-chat-lead-gen' ),
			esc_attr__( 'Aumenta quantità', 'woo-chat-lead-gen' )
		);
	}

	/**
	 * @return string SVG inline dell'icona WhatsApp/Telegram.
	 */
	private function get_icon() {
		if ( 'telegram' === WCLG_Settings::get( 'channel' ) ) {
			$path = 'M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z';
		} else {
			$path = 'M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.87 9.87 0 004.74 1.21h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0012.04 2zm5.8 14.16c-.24.68-1.42 1.31-1.96 1.36-.5.05-1.14.07-1.83-.11-.42-.13-.97-.31-1.67-.61-2.94-1.27-4.86-4.23-5.01-4.43-.14-.2-1.19-1.58-1.19-3.02s.76-2.14 1.03-2.44c.27-.3.58-.37.78-.37.19 0 .39 0 .56.01.18.01.42-.07.66.5.24.58.83 2.02.9 2.17.07.15.12.32.02.52-.1.2-.15.32-.29.49-.15.17-.31.38-.44.51-.15.15-.3.31-.13.6.17.3.76 1.25 1.63 2.02 1.12 1 2.06 1.31 2.35 1.46.3.15.47.12.64-.07.17-.2.74-.86.94-1.16.2-.3.39-.25.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.72-.17 1.4z';
		}

		return sprintf(
			'<svg class="wclg-button__icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="%s"/></svg>',
			esc_attr( $path )
		);
	}

	/**
	 * @return string Micro-copy sotto il pulsante.
	 */
	private function get_reassurance() {
		$text = apply_filters(
			'wclg_reassurance_text',
			__( 'Risposta in pochi minuti · Nessun pagamento online', 'woo-chat-lead-gen' )
		);
		return $text ? '<p class="wclg-cta__note">' . esc_html( $text ) . '</p>' : '';
	}

	/* --------------------------------------------------------------------- *
	 * Sticky bar & shortcode
	 * --------------------------------------------------------------------- */

	/**
	 * Barra CTA fissa in fondo alla scheda prodotto su mobile.
	 *
	 * Non duplica il link: clona via JS quello principale, così resta
	 * sincronizzato con la variante selezionata.
	 */
	public function render_sticky_bar() {
		if ( ! function_exists( 'is_product' ) || ! is_product() ) {
			return;
		}
		$product = wc_get_product( get_queried_object_id() );
		if ( ! $product instanceof WC_Product ) {
			return;
		}
		?>
		<div class="wclg-sticky" data-wclg-sticky hidden>
			<div class="wclg-sticky__info">
				<span class="wclg-sticky__title"><?php echo esc_html( $product->get_name() ); ?></span>
				<?php if ( ! WCLG_Settings::is( 'hide_price' ) ) : ?>
					<span class="wclg-sticky__price" data-wclg-sticky-price><?php echo wp_kses_post( $product->get_price_html() ); ?></span>
				<?php endif; ?>
			</div>
			<a href="#" class="button wclg-button wclg-button--sticky" data-wclg-sticky-link>
				<?php echo esc_html( WCLG_Settings::get( 'button_label' ) ); ?>
			</a>
		</div>
		<?php
	}

	/**
	 * Shortcode [wclg_chat_button id="123" label="Ordina ora"].
	 *
	 * @param array $atts Attributi.
	 * @return string
	 */
	public function shortcode( $atts ) {
		$atts = shortcode_atts(
			array(
				'id'    => 0,
				'label' => WCLG_Settings::get( 'button_label' ),
			),
			$atts,
			'wclg_chat_button'
		);

		$product = $atts['id'] ? wc_get_product( (int) $atts['id'] ) : ( $GLOBALS['product'] ?? null );
		if ( ! $product instanceof WC_Product ) {
			return '';
		}

		$this->enqueue_assets();

		return $this->get_button_html(
			$product,
			array(
				'context'  => 'shortcode',
				'label'    => sanitize_text_field( $atts['label'] ),
				'quantity' => false,
			)
		);
	}
}
