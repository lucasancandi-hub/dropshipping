<?php
/**
 * Numerazione progressiva e registrazione locale dell'ordine chat.
 *
 * Il flusso è volutamente senza JavaScript: il pulsante del carrello è un
 * link normale verso `?wclg_order=1`, intercettato qui su `template_redirect`.
 * Il gestore genera il codice, registra l'ordine e reindirizza a WhatsApp.
 * Nessuna finestra aperta da callback asincrone, quindi nessun popup bloccato.
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Order {

	const STATUS         = 'wclg-chat';
	const CODE_META      = '_wclg_order_code';
	const SESSION_KEY    = 'wclg_order';
	const COUNTER_PREFIX = 'wclg_order_counter_';
	const QUERY_ARG      = 'wclg_order';
	const NONCE_ACTION   = 'wclg_chat_order';

	/**
	 * @var WCLG_Order|null
	 */
	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'init', array( $this, 'register_status' ) );
		add_filter( 'wc_order_statuses', array( $this, 'add_status' ) );
		add_action( 'template_redirect', array( $this, 'handle_request' ), 5 );
		add_filter( 'woocommerce_order_number', array( $this, 'display_order_number' ), 10, 2 );
	}

	/* --------------------------------------------------------------------- *
	 * Stato ordine dedicato
	 * --------------------------------------------------------------------- */

	public function register_status() {
		register_post_status(
			'wc-' . self::STATUS,
			array(
				'label'                     => _x( 'In attesa in chat', 'Stato ordine', 'woo-chat-lead-gen' ),
				'public'                    => false,
				'exclude_from_search'       => false,
				'show_in_admin_all_list'    => true,
				'show_in_admin_status_list' => true,
				/* translators: %s: numero di ordini. */
				'label_count'               => _n_noop( 'In attesa in chat <span class="count">(%s)</span>', 'In attesa in chat <span class="count">(%s)</span>', 'woo-chat-lead-gen' ),
			)
		);
	}

	/**
	 * @param array $statuses Stati registrati in WooCommerce.
	 * @return array
	 */
	public function add_status( $statuses ) {
		$statuses[ 'wc-' . self::STATUS ] = _x( 'In attesa in chat', 'Stato ordine', 'woo-chat-lead-gen' );
		return $statuses;
	}

	/**
	 * In elenco ordini mostra ORD-2026-001 al posto dell'ID interno.
	 *
	 * @param string   $number Numero corrente.
	 * @param WC_Order $order  Ordine.
	 * @return string
	 */
	public function display_order_number( $number, $order ) {
		$code = $order instanceof WC_Order ? $order->get_meta( self::CODE_META ) : '';
		return $code ? $code : $number;
	}

	/* --------------------------------------------------------------------- *
	 * Codice progressivo
	 * --------------------------------------------------------------------- */

	/**
	 * Prossimo codice ordine, azzerato ogni anno: ORD-2026-001.
	 *
	 * @return string
	 */
	public static function next_code() {
		$year   = current_time( 'Y' );
		$number = self::increment( self::COUNTER_PREFIX . $year );

		$code = sprintf(
			'%s-%s-%0' . max( 1, (int) WCLG_Settings::get( 'order_digits', 3 ) ) . 'd',
			WCLG_Settings::get( 'order_prefix', 'ORD' ),
			$year,
			$number
		);

		/**
		 * Filtra il codice ordine generato.
		 *
		 * @param string $code   Codice.
		 * @param int    $number Progressivo dell'anno.
		 * @param string $year   Anno.
		 */
		return apply_filters( 'wclg_order_code', $code, $number, $year );
	}

	/**
	 * Incremento atomico del contatore.
	 *
	 * `LAST_INSERT_ID(option_value + 1)` fa leggere e incrementare al database
	 * in una sola istruzione: due richieste simultanee non possono ottenere lo
	 * stesso numero, cosa che invece succederebbe con get_option/update_option.
	 *
	 * @param string $key Nome dell'opzione contatore.
	 * @return int
	 */
	private static function increment( $key ) {
		global $wpdb;

		$sql = $wpdb->prepare(
			"UPDATE {$wpdb->options} SET option_value = LAST_INSERT_ID(option_value + 1) WHERE option_name = %s",
			$key
		);

		// phpcs:disable WordPress.DB.DirectDatabaseQuery -- serve un incremento atomico.
		if ( $wpdb->query( $sql ) ) {
			wp_cache_delete( $key, 'options' );
			return (int) $wpdb->insert_id;
		}

		// Primo ordine dell'anno: il contatore non esiste ancora.
		if ( add_option( $key, '1', '', 'no' ) ) {
			return 1;
		}

		// Un'altra richiesta l'ha creato nel frattempo: riprova l'incremento.
		$wpdb->query( $sql );
		// phpcs:enable WordPress.DB.DirectDatabaseQuery
		wp_cache_delete( $key, 'options' );

		return max( 1, (int) $wpdb->insert_id );
	}

	/**
	 * Codice per il carrello corrente.
	 *
	 * Finché il carrello non cambia il codice resta lo stesso: riaprire la
	 * chat non brucia numeri né crea ordini doppioni.
	 *
	 * @return array{code:string,order_id:int,fresh:bool}
	 */
	public static function resolve_code() {
		$hash    = WCLG_Cart::get_hash();
		$session = ( function_exists( 'WC' ) && WC()->session ) ? WC()->session->get( self::SESSION_KEY ) : null;

		if ( is_array( $session ) && isset( $session['hash'], $session['code'] ) && $session['hash'] === $hash ) {
			return array(
				'code'     => $session['code'],
				'order_id' => (int) ( $session['order_id'] ?? 0 ),
				'fresh'    => false,
			);
		}

		$code     = self::next_code();
		$order_id = WCLG_Settings::is( 'create_order' ) ? self::create_order( $code ) : 0;

		if ( function_exists( 'WC' ) && WC()->session ) {
			WC()->session->set(
				self::SESSION_KEY,
				array(
					'hash'     => $hash,
					'code'     => $code,
					'order_id' => $order_id,
				)
			);
		}

		return array(
			'code'     => $code,
			'order_id' => $order_id,
			'fresh'    => true,
		);
	}

	/* --------------------------------------------------------------------- *
	 * Ordine WooCommerce
	 * --------------------------------------------------------------------- */

	/**
	 * Registra l'ordine in WooCommerce nello stato "In attesa in chat".
	 *
	 * Non ci sono dati di fatturazione: verranno raccolti in conversazione.
	 * L'ordine serve al negoziante per ritrovare la richiesta in bacheca.
	 *
	 * @param string $code Codice progressivo.
	 * @return int ID ordine, 0 se la creazione fallisce.
	 */
	public static function create_order( $code ) {
		if ( ! function_exists( 'wc_create_order' ) || ! WC()->cart || WC()->cart->is_empty() ) {
			return 0;
		}

		try {
			$order = wc_create_order( array( 'created_via' => 'wclg-chat' ) );
			if ( is_wp_error( $order ) ) {
				return 0;
			}

			foreach ( WC()->cart->get_cart() as $cart_item ) {
				if ( ! isset( $cart_item['data'] ) || ! $cart_item['data'] instanceof WC_Product ) {
					continue;
				}
				$order->add_product(
					$cart_item['data'],
					$cart_item['quantity'],
					array(
						'subtotal' => (float) ( $cart_item['line_subtotal'] ?? 0 ),
						'total'    => (float) ( $cart_item['line_total'] ?? 0 ),
					)
				);
			}

			$shipping = WCLG_Shipping::estimate();
			if ( ! $shipping['on_request'] ) {
				$item = new WC_Order_Item_Shipping();
				$item->set_method_title( __( 'Spedizione stimata', 'woo-chat-lead-gen' ) );
				$item->set_total( (float) $shipping['amount'] );
				$order->add_item( $item );
			}

			$order->set_customer_id( get_current_user_id() );
			$order->update_meta_data( self::CODE_META, $code );
			$order->calculate_totals( false );
			$order->set_status( self::STATUS );
			$order->add_order_note(
				sprintf(
					/* translators: 1: codice ordine, 2: stima spedizione. */
					__( 'Richiesta inviata in chat. Codice %1$s. Spedizione: %2$s.', 'woo-chat-lead-gen' ),
					$code,
					$shipping['label']
				)
			);
			$order->save();

			/**
			 * Ordine chat appena creato (es. per notifiche o CRM).
			 *
			 * @param WC_Order $order Ordine.
			 * @param string   $code  Codice progressivo.
			 */
			do_action( 'wclg_order_created', $order, $code );

			return $order->get_id();
		} catch ( Exception $exception ) {
			// Il messaggio va comunque inviato: la chat non deve dipendere dal DB.
			if ( function_exists( 'wc_get_logger' ) ) {
				wc_get_logger()->error(
					'Creazione ordine chat fallita: ' . $exception->getMessage(),
					array( 'source' => 'woo-chat-lead-gen' )
				);
			}
			return 0;
		}
	}

	/* --------------------------------------------------------------------- *
	 * Endpoint
	 * --------------------------------------------------------------------- */

	/**
	 * URL del pulsante "Invia ordine".
	 *
	 * @return string
	 */
	public static function get_chat_url() {
		if ( ! function_exists( 'wc_get_cart_url' ) ) {
			return '';
		}

		return add_query_arg(
			array(
				self::QUERY_ARG => 1,
				'_wpnonce'      => wp_create_nonce( self::NONCE_ACTION ),
			),
			wc_get_cart_url()
		);
	}

	/**
	 * Intercetta il click, prepara l'ordine e manda a WhatsApp.
	 */
	public function handle_request() {
		if ( is_admin() || empty( $_GET[ self::QUERY_ARG ] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			return;
		}

		$cart_url = wc_get_cart_url();

		// Il nonce tiene fuori i crawler: nessun ordine creato dai bot.
		$nonce = isset( $_GET['_wpnonce'] ) ? sanitize_text_field( wp_unslash( $_GET['_wpnonce'] ) ) : '';
		if ( ! wp_verify_nonce( $nonce, self::NONCE_ACTION ) ) {
			wc_add_notice( __( 'Sessione scaduta: ricarica la pagina e riprova.', 'woo-chat-lead-gen' ), 'error' );
			wp_safe_redirect( $cart_url );
			exit;
		}

		if ( ! WC()->cart || WC()->cart->is_empty() ) {
			wc_add_notice( __( 'Il carrello è vuoto.', 'woo-chat-lead-gen' ), 'notice' );
			wp_safe_redirect( $cart_url );
			exit;
		}

		$resolved = self::resolve_code();
		$message  = WCLG_Message::build_cart_message( $resolved['code'] );
		$url      = WCLG_Message::build_url( $message );

		if ( '' === $url ) {
			wc_add_notice( __( 'Canale chat non configurato.', 'woo-chat-lead-gen' ), 'error' );
			wp_safe_redirect( $cart_url );
			exit;
		}

		/**
		 * Ultimo passaggio prima del redirect verso la chat.
		 *
		 * @param string $code     Codice ordine.
		 * @param int    $order_id ID ordine WooCommerce (0 se non creato).
		 * @param string $message  Messaggio in chiaro.
		 */
		do_action( 'wclg_before_chat_redirect', $resolved['code'], $resolved['order_id'], $message );

		// Destinazione esterna: wp_safe_redirect la bloccherebbe.
		wp_redirect( $url, 302 ); // phpcs:ignore WordPress.Security.SafeRedirect.wp_redirect_wp_redirect
		exit;
	}
}
