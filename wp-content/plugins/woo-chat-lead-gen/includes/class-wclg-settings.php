<?php
/**
 * Impostazioni del plugin (WooCommerce > Chat Lead Gen).
 *
 * Tutte le opzioni vivono in un unico array `wclg_settings` così da avere
 * una sola riga in wp_options e un solo punto di sanitizzazione.
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Settings {

	const OPTION = 'wclg_settings';

	/**
	 * @var WCLG_Settings|null
	 */
	private static $instance = null;

	/**
	 * Cache runtime delle opzioni risolte.
	 *
	 * @var array|null
	 */
	private static $cache = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'admin_menu', array( $this, 'register_menu' ) );
		add_action( 'admin_init', array( $this, 'register_settings' ) );
		add_filter( 'plugin_action_links_' . plugin_basename( WCLG_FILE ), array( $this, 'action_links' ) );
	}

	/* --------------------------------------------------------------------- *
	 * Lettura opzioni
	 * --------------------------------------------------------------------- */

	/**
	 * Valori di default.
	 *
	 * @return array
	 */
	public static function defaults() {
		return array(
			// Flusso: 'cart' = carrello + invio ordine, 'direct' = dal prodotto alla chat.
			'order_flow'            => 'cart',
			'enabled'               => 'yes',
			'channel'               => 'whatsapp',
			'phone'                 => '393408857026',
			'telegram_user'         => '',
			'button_label'          => __( 'Ordina via WhatsApp', 'woo-chat-lead-gen' ),
			'loop_button_label'     => __( 'Ordina in chat', 'woo-chat-lead-gen' ),
			'loop_button_action'    => 'product',
			'message_template'      => self::default_template(),
			'disable_cart'          => 'yes',
			'hide_price'            => 'no',
			'show_quantity'         => 'yes',
			'sticky_mobile'         => 'yes',
			'load_css'              => 'yes',
			'new_tab'               => 'yes',
			// Carrello chat.
			'cart_button_label'     => __( 'Invia ordine su WhatsApp', 'woo-chat-lead-gen' ),
			'cart_drawer'           => 'yes',
			'single_chat_link'      => 'yes',
			'cart_message_template' => self::default_cart_template(),
			'cart_item_template'    => __( '• {name} - Taglia: {variant} - Q.tà: {qty} - Prezzo: {price}', 'woo-chat-lead-gen' ),
			'price_request_label'   => __( 'Prezzo da concordare in chat', 'woo-chat-lead-gen' ),
			// Numerazione ordini.
			'order_prefix'          => 'ORD',
			'order_digits'          => '3',
			'create_order'          => 'yes',
			// Spedizione.
			'shipping_mode'         => 'flat',
			'shipping_flat'         => '7.90',
			'shipping_rate'         => '2.00',
			'shipping_base'         => '0',
			'shipping_free_over'    => '99',
		);
	}

	/**
	 * Template del messaggio precompilato.
	 *
	 * Le righe che contengono solo segnaposto vuoti vengono rimosse a runtime
	 * (es. "Taglia:" sparisce sui prodotti senza varianti).
	 *
	 * @return string
	 */
	public static function default_template() {
		return implode(
			"\n",
			array(
				__( 'Ciao! 👋 Vorrei ordinare questo articolo:', 'woo-chat-lead-gen' ),
				'',
				'*{product}*',
				__( 'Taglia: {variant}', 'woo-chat-lead-gen' ),
				__( 'Quantità: {qty}', 'woo-chat-lead-gen' ),
				__( 'Prezzo: {price}', 'woo-chat-lead-gen' ),
				__( 'Codice: {sku}', 'woo-chat-lead-gen' ),
				'',
				'{url}',
			)
		);
	}

	/**
	 * Template del messaggio d'ordine generato dal carrello.
	 *
	 * @return string
	 */
	public static function default_cart_template() {
		return implode(
			"\n",
			array(
				__( '🛒 *Nuovo Ordine #{order}*', 'woo-chat-lead-gen' ),
				'----------------------------------',
				'{items}',
				'----------------------------------',
				__( '📦 Spedizione: {shipping}', 'woo-chat-lead-gen' ),
				__( '💰 *Totale Stimato: {total}*', 'woo-chat-lead-gen' ),
				'',
				__( 'Ciao! Vorrei confermare questo ordine.', 'woo-chat-lead-gen' ),
			)
		);
	}

	/**
	 * Tutte le opzioni, con default applicati.
	 *
	 * @return array
	 */
	public static function all() {
		if ( null === self::$cache ) {
			$stored     = get_option( self::OPTION, array() );
			self::$cache = wp_parse_args( is_array( $stored ) ? $stored : array(), self::defaults() );
		}
		/**
		 * Permette di sovrascrivere le impostazioni via codice (es. multisito).
		 *
		 * @param array $settings Impostazioni risolte.
		 */
		return apply_filters( 'wclg_settings', self::$cache );
	}

	/**
	 * @param string $key     Chiave opzione.
	 * @param mixed  $default Valore di fallback.
	 * @return mixed
	 */
	public static function get( $key, $default = '' ) {
		$settings = self::all();
		return isset( $settings[ $key ] ) ? $settings[ $key ] : $default;
	}

	/**
	 * @param string $key Chiave opzione booleana ('yes'/'no').
	 * @return bool
	 */
	public static function is( $key ) {
		return 'yes' === self::get( $key, 'no' );
	}

	/**
	 * Il plugin è operativo solo se il canale ha un destinatario valido.
	 *
	 * @return bool
	 */
	public static function is_enabled() {
		if ( ! self::is( 'enabled' ) ) {
			return false;
		}
		return 'telegram' === self::get( 'channel' )
			? '' !== self::get( 'telegram_user' )
			: '' !== self::get( 'phone' );
	}

	/* --------------------------------------------------------------------- *
	 * Admin
	 * --------------------------------------------------------------------- */

	public function register_menu() {
		add_submenu_page(
			'woocommerce',
			__( 'Chat Lead Gen', 'woo-chat-lead-gen' ),
			__( 'Chat Lead Gen', 'woo-chat-lead-gen' ),
			'manage_woocommerce',
			'wclg-settings',
			array( $this, 'render_page' )
		);
	}

	public function register_settings() {
		register_setting(
			'wclg_settings_group',
			self::OPTION,
			array(
				'type'              => 'array',
				'sanitize_callback' => array( $this, 'sanitize' ),
				'default'           => self::defaults(),
			)
		);
	}

	/**
	 * Sanitizza l'intero array di opzioni.
	 *
	 * @param mixed $input Dati grezzi dal form.
	 * @return array
	 */
	public function sanitize( $input ) {
		$input     = is_array( $input ) ? $input : array();
		$defaults  = self::defaults();
		$clean     = array();
		$checkboxes = array(
			'enabled',
			'disable_cart',
			'hide_price',
			'show_quantity',
			'sticky_mobile',
			'load_css',
			'new_tab',
			'cart_drawer',
			'single_chat_link',
			'create_order',
		);

		foreach ( $checkboxes as $key ) {
			$clean[ $key ] = ! empty( $input[ $key ] ) ? 'yes' : 'no';
		}

		$clean['channel'] = in_array( $input['channel'] ?? '', array( 'whatsapp', 'telegram' ), true )
			? $input['channel']
			: $defaults['channel'];

		$clean['loop_button_action'] = in_array( $input['loop_button_action'] ?? '', array( 'product', 'chat' ), true )
			? $input['loop_button_action']
			: $defaults['loop_button_action'];

		$clean['order_flow'] = in_array( $input['order_flow'] ?? '', array( 'cart', 'direct' ), true )
			? $input['order_flow']
			: $defaults['order_flow'];

		$clean['shipping_mode'] = in_array( $input['shipping_mode'] ?? '', array( 'flat', 'quantity', 'weight', 'woo', 'none' ), true )
			? $input['shipping_mode']
			: $defaults['shipping_mode'];

		// Importi: wc_format_decimal normalizza la virgola decimale italiana.
		foreach ( array( 'shipping_flat', 'shipping_rate', 'shipping_base', 'shipping_free_over' ) as $key ) {
			$clean[ $key ] = wc_format_decimal( $input[ $key ] ?? $defaults[ $key ], false, true );
			if ( '' === $clean[ $key ] || (float) $clean[ $key ] < 0 ) {
				$clean[ $key ] = '0';
			}
		}

		// Prefisso ordine: solo lettere, cifre e trattini (finisce in un codice).
		$prefix                 = strtoupper( sanitize_text_field( $input['order_prefix'] ?? '' ) );
		$prefix                 = preg_replace( '/[^A-Z0-9\-]/', '', $prefix );
		$clean['order_prefix']  = '' !== $prefix ? $prefix : $defaults['order_prefix'];
		$clean['order_digits']  = (string) min( 8, max( 1, (int) ( $input['order_digits'] ?? 3 ) ) );

		$clean['cart_button_label']   = sanitize_text_field( $input['cart_button_label'] ?? $defaults['cart_button_label'] );
		$clean['price_request_label'] = sanitize_text_field( $input['price_request_label'] ?? $defaults['price_request_label'] );

		foreach ( array( 'cart_message_template', 'cart_item_template' ) as $key ) {
			$value         = trim( wp_unslash( (string) ( $input[ $key ] ?? '' ) ) );
			$clean[ $key ] = '' !== $value ? sanitize_textarea_field( $value ) : $defaults[ $key ];
		}

		// Numero in formato internazionale, solo cifre (es. 393401234567).
		$clean['phone']         = preg_replace( '/[^0-9]/', '', (string) ( $input['phone'] ?? '' ) );
		$clean['telegram_user'] = ltrim( sanitize_text_field( $input['telegram_user'] ?? '' ), '@' );

		$clean['button_label']      = sanitize_text_field( $input['button_label'] ?? $defaults['button_label'] );
		$clean['loop_button_label'] = sanitize_text_field( $input['loop_button_label'] ?? $defaults['loop_button_label'] );

		$template                  = wp_unslash( (string) ( $input['message_template'] ?? '' ) );
		$clean['message_template'] = trim( $template ) ? sanitize_textarea_field( $template ) : $defaults['message_template'];

		self::$cache = null; // Invalida la cache runtime.
		return $clean;
	}

	/**
	 * @param array $links Link azione nella lista plugin.
	 * @return array
	 */
	public function action_links( $links ) {
		$url = admin_url( 'admin.php?page=wclg-settings' );
		array_unshift( $links, '<a href="' . esc_url( $url ) . '">' . esc_html__( 'Impostazioni', 'woo-chat-lead-gen' ) . '</a>' );
		return $links;
	}

	public function render_page() {
		if ( ! current_user_can( 'manage_woocommerce' ) ) {
			wp_die( esc_html__( 'Permessi insufficienti.', 'woo-chat-lead-gen' ) );
		}

		$settings = self::all();
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'Chat Lead Gen', 'woo-chat-lead-gen' ); ?></h1>
			<p class="description">
				<?php esc_html_e( 'Disattiva carrello e pagamenti e trasforma ogni scheda prodotto in una richiesta d\'ordine via chat.', 'woo-chat-lead-gen' ); ?>
			</p>

			<?php if ( self::is( 'enabled' ) && ! self::is_enabled() ) : ?>
				<div class="notice notice-warning inline">
					<p><?php esc_html_e( 'Inserisci il numero WhatsApp (o lo username Telegram) per attivare i pulsanti.', 'woo-chat-lead-gen' ); ?></p>
				</div>
			<?php endif; ?>

			<form method="post" action="options.php">
				<?php settings_fields( 'wclg_settings_group' ); ?>
				<table class="form-table" role="presentation">
					<tbody>
					<?php
					$this->checkbox_row( 'enabled', __( 'Attiva il plugin', 'woo-chat-lead-gen' ), __( 'Disattiva per tornare a WooCommerce standard senza disinstallare.', 'woo-chat-lead-gen' ), $settings );
					?>
					<tr>
						<th scope="row"><?php esc_html_e( 'Flusso d\'ordine', 'woo-chat-lead-gen' ); ?></th>
						<td>
							<fieldset>
								<label>
									<input type="radio" name="<?php echo esc_attr( self::OPTION ); ?>[order_flow]" value="cart" <?php checked( $settings['order_flow'], 'cart' ); ?>>
									<strong><?php esc_html_e( 'Carrello + invio ordine in chat', 'woo-chat-lead-gen' ); ?></strong><br>
									<span class="description"><?php esc_html_e( 'L\'utente aggiunge più articoli, vede il riepilogo con la spedizione stimata e invia l\'ordine completo con un numero progressivo.', 'woo-chat-lead-gen' ); ?></span>
								</label>
								<br><br>
								<label>
									<input type="radio" name="<?php echo esc_attr( self::OPTION ); ?>[order_flow]" value="direct" <?php checked( $settings['order_flow'], 'direct' ); ?>>
									<strong><?php esc_html_e( 'Diretto: dal prodotto alla chat', 'woo-chat-lead-gen' ); ?></strong><br>
									<span class="description"><?php esc_html_e( 'Nessun carrello: ogni scheda prodotto apre la chat con quel singolo articolo.', 'woo-chat-lead-gen' ); ?></span>
								</label>
							</fieldset>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-channel"><?php esc_html_e( 'Canale', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<select name="<?php echo esc_attr( self::OPTION ); ?>[channel]" id="wclg-channel">
								<option value="whatsapp" <?php selected( $settings['channel'], 'whatsapp' ); ?>>WhatsApp</option>
								<option value="telegram" <?php selected( $settings['channel'], 'telegram' ); ?>>Telegram</option>
							</select>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-phone"><?php esc_html_e( 'Numero WhatsApp', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<input type="text" class="regular-text" id="wclg-phone" name="<?php echo esc_attr( self::OPTION ); ?>[phone]" value="<?php echo esc_attr( $settings['phone'] ); ?>" placeholder="393401234567">
							<p class="description"><?php esc_html_e( 'Formato internazionale senza + e senza spazi (es. 393401234567).', 'woo-chat-lead-gen' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-telegram"><?php esc_html_e( 'Username Telegram', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<input type="text" class="regular-text" id="wclg-telegram" name="<?php echo esc_attr( self::OPTION ); ?>[telegram_user]" value="<?php echo esc_attr( $settings['telegram_user'] ); ?>" placeholder="iltuoshop">
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-label"><?php esc_html_e( 'Etichetta pulsante prodotto (flusso diretto)', 'woo-chat-lead-gen' ); ?></label></th>
						<td><input type="text" class="regular-text" id="wclg-label" name="<?php echo esc_attr( self::OPTION ); ?>[button_label]" value="<?php echo esc_attr( $settings['button_label'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-loop-label"><?php esc_html_e( 'Etichetta pulsante catalogo (flusso diretto)', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<input type="text" class="regular-text" id="wclg-loop-label" name="<?php echo esc_attr( self::OPTION ); ?>[loop_button_label]" value="<?php echo esc_attr( $settings['loop_button_label'] ); ?>">
							<p>
								<label>
									<input type="radio" name="<?php echo esc_attr( self::OPTION ); ?>[loop_button_action]" value="product" <?php checked( $settings['loop_button_action'], 'product' ); ?>>
									<?php esc_html_e( 'Porta alla scheda prodotto (consigliato: l\'utente sceglie la taglia)', 'woo-chat-lead-gen' ); ?>
								</label><br>
								<label>
									<input type="radio" name="<?php echo esc_attr( self::OPTION ); ?>[loop_button_action]" value="chat" <?php checked( $settings['loop_button_action'], 'chat' ); ?>>
									<?php esc_html_e( 'Apre subito la chat', 'woo-chat-lead-gen' ); ?>
								</label>
							</p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-template"><?php esc_html_e( 'Messaggio prodotto (flusso diretto)', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<textarea id="wclg-template" name="<?php echo esc_attr( self::OPTION ); ?>[message_template]" rows="10" class="large-text code"><?php echo esc_textarea( $settings['message_template'] ); ?></textarea>
							<p class="description">
								<?php esc_html_e( 'Segnaposto disponibili:', 'woo-chat-lead-gen' ); ?>
								<code>{product}</code> <code>{price}</code> <code>{variant}</code> <code>{sku}</code>
								<code>{qty}</code> <code>{url}</code> <code>{shop}</code><br>
								<?php esc_html_e( 'Le righe con soli segnaposto vuoti vengono rimosse automaticamente.', 'woo-chat-lead-gen' ); ?>
							</p>
						</td>
					</tr>
					<?php
					$this->checkbox_row( 'disable_cart', __( 'Disattiva carrello e pagamenti', 'woo-chat-lead-gen' ), __( 'Solo nel flusso diretto: blocca gli aggiunta-al-carrello e reindirizza carrello/checkout. Nel flusso con carrello restano attivi solo i pagamenti disattivati.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'show_quantity', __( 'Selettore quantità', 'woo-chat-lead-gen' ), __( 'Solo nel flusso diretto: campo quantità accanto al pulsante chat.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'hide_price', __( 'Nascondi i prezzi', 'woo-chat-lead-gen' ), __( 'Utile per listini su richiesta.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'sticky_mobile', __( 'CTA fissa su mobile', 'woo-chat-lead-gen' ), __( 'Solo nel flusso diretto: barra sempre visibile nella scheda prodotto.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'new_tab', __( 'Apri la chat in una nuova scheda', 'woo-chat-lead-gen' ), '', $settings );
					$this->checkbox_row( 'load_css', __( 'Carica il CSS del plugin', 'woo-chat-lead-gen' ), __( 'Disattiva se preferisci gestire lo stile dal tema.', 'woo-chat-lead-gen' ), $settings );
					?>
					</tbody>
				</table>

				<h2><?php esc_html_e( 'Carrello e invio ordine', 'woo-chat-lead-gen' ); ?></h2>
				<p class="description"><?php esc_html_e( 'Impostazioni usate solo con il flusso "Carrello + invio ordine in chat".', 'woo-chat-lead-gen' ); ?></p>
				<table class="form-table" role="presentation">
					<tbody>
					<tr>
						<th scope="row"><label for="wclg-cart-label"><?php esc_html_e( 'Etichetta pulsante carrello', 'woo-chat-lead-gen' ); ?></label></th>
						<td><input type="text" class="regular-text" id="wclg-cart-label" name="<?php echo esc_attr( self::OPTION ); ?>[cart_button_label]" value="<?php echo esc_attr( $settings['cart_button_label'] ); ?>"></td>
					</tr>
					<?php
					$this->checkbox_row( 'cart_drawer', __( 'Drawer laterale', 'woo-chat-lead-gen' ), __( 'Pannello carrello che si apre di lato con pulsante flottante e contatore.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'single_chat_link', __( 'Link "chiedi info" sul prodotto', 'woo-chat-lead-gen' ), __( 'Aggiunge un link discreto alla chat sotto il pulsante "Aggiungi al carrello".', 'woo-chat-lead-gen' ), $settings );
					?>
					<tr>
						<th scope="row"><label for="wclg-cart-template"><?php esc_html_e( 'Messaggio d\'ordine', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<textarea id="wclg-cart-template" name="<?php echo esc_attr( self::OPTION ); ?>[cart_message_template]" rows="10" class="large-text code"><?php echo esc_textarea( $settings['cart_message_template'] ); ?></textarea>
							<p class="description">
								<?php esc_html_e( 'Segnaposto:', 'woo-chat-lead-gen' ); ?>
								<code>{order}</code> <code>{items}</code> <code>{subtotal}</code>
								<code>{shipping}</code> <code>{total}</code> <code>{count}</code>
								<code>{url}</code> <code>{shop}</code>
							</p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-item-template"><?php esc_html_e( 'Riga articolo', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<input type="text" class="large-text code" id="wclg-item-template" name="<?php echo esc_attr( self::OPTION ); ?>[cart_item_template]" value="<?php echo esc_attr( $settings['cart_item_template'] ); ?>">
							<p class="description">
								<?php esc_html_e( 'Segnaposto:', 'woo-chat-lead-gen' ); ?>
								<code>{name}</code> <code>{variant}</code> <code>{qty}</code> <code>{price}</code> <code>{sku}</code>.
								<?php esc_html_e( 'I segmenti separati da " - " con segnaposto vuoti spariscono: su un prodotto senza taglia non resta "Taglia:" a vuoto.', 'woo-chat-lead-gen' ); ?>
							</p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-price-label"><?php esc_html_e( 'Etichetta prezzo su richiesta', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<input type="text" class="regular-text" id="wclg-price-label" name="<?php echo esc_attr( self::OPTION ); ?>[price_request_label]" value="<?php echo esc_attr( $settings['price_request_label'] ); ?>">
							<p class="description"><?php esc_html_e( 'Mostrata sui prodotti senza prezzo o marcati "Prezzo da concordare" nella scheda prodotto.', 'woo-chat-lead-gen' ); ?></p>
						</td>
					</tr>
					</tbody>
				</table>

				<h2><?php esc_html_e( 'Spedizione stimata', 'woo-chat-lead-gen' ); ?></h2>
				<table class="form-table" role="presentation">
					<tbody>
					<tr>
						<th scope="row"><label for="wclg-shipping-mode"><?php esc_html_e( 'Calcolo', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<select name="<?php echo esc_attr( self::OPTION ); ?>[shipping_mode]" id="wclg-shipping-mode">
								<option value="flat" <?php selected( $settings['shipping_mode'], 'flat' ); ?>><?php esc_html_e( 'Tariffa fissa', 'woo-chat-lead-gen' ); ?></option>
								<option value="quantity" <?php selected( $settings['shipping_mode'], 'quantity' ); ?>><?php esc_html_e( 'Base + tariffa per articolo', 'woo-chat-lead-gen' ); ?></option>
								<option value="weight" <?php selected( $settings['shipping_mode'], 'weight' ); ?>><?php esc_html_e( 'Base + tariffa al kg', 'woo-chat-lead-gen' ); ?></option>
								<option value="woo" <?php selected( $settings['shipping_mode'], 'woo' ); ?>><?php esc_html_e( 'Spedizioni native WooCommerce', 'woo-chat-lead-gen' ); ?></option>
								<option value="none" <?php selected( $settings['shipping_mode'], 'none' ); ?>><?php esc_html_e( 'Sempre da concordare in chat', 'woo-chat-lead-gen' ); ?></option>
							</select>
						</td>
					</tr>
					<?php
					$this->number_row( 'shipping_flat', __( 'Tariffa fissa', 'woo-chat-lead-gen' ), __( 'Usata dalla tariffa fissa e come ripiego per le spedizioni native.', 'woo-chat-lead-gen' ), $settings );
					$this->number_row( 'shipping_base', __( 'Quota base', 'woo-chat-lead-gen' ), __( 'Sommata al calcolo per articolo o a peso.', 'woo-chat-lead-gen' ), $settings );
					$this->number_row( 'shipping_rate', __( 'Tariffa per articolo / per kg', 'woo-chat-lead-gen' ), '', $settings );
					$this->number_row( 'shipping_free_over', __( 'Spedizione gratuita oltre', 'woo-chat-lead-gen' ), __( '0 per disattivare la soglia.', 'woo-chat-lead-gen' ), $settings );
					?>
					</tbody>
				</table>

				<h2><?php esc_html_e( 'Numerazione ordini', 'woo-chat-lead-gen' ); ?></h2>
				<table class="form-table" role="presentation">
					<tbody>
					<tr>
						<th scope="row"><label for="wclg-order-prefix"><?php esc_html_e( 'Formato codice', 'woo-chat-lead-gen' ); ?></label></th>
						<td>
							<input type="text" class="small-text" id="wclg-order-prefix" name="<?php echo esc_attr( self::OPTION ); ?>[order_prefix]" value="<?php echo esc_attr( $settings['order_prefix'] ); ?>">
							<input type="number" class="small-text" min="1" max="8" name="<?php echo esc_attr( self::OPTION ); ?>[order_digits]" value="<?php echo esc_attr( $settings['order_digits'] ); ?>">
							<p class="description">
								<?php
								printf(
									/* translators: %s: esempio di codice ordine. */
									esc_html__( 'Prefisso e numero di cifre. Risultato: %s. Il progressivo riparte da 1 ogni anno.', 'woo-chat-lead-gen' ),
									'<code>' . esc_html(
										sprintf(
											'%s-%s-%0' . max( 1, (int) $settings['order_digits'] ) . 'd',
											$settings['order_prefix'],
											current_time( 'Y' ),
											1
										)
									) . '</code>'
								);
								?>
							</p>
						</td>
					</tr>
					<?php
					$this->checkbox_row( 'create_order', __( 'Registra l\'ordine in WooCommerce', 'woo-chat-lead-gen' ), __( 'Crea un ordine nello stato "In attesa in chat", così la richiesta resta in bacheca ordini.', 'woo-chat-lead-gen' ), $settings );
					?>
					</tbody>
				</table>
				<?php submit_button(); ?>
			</form>

			<h2><?php esc_html_e( 'Shortcode', 'woo-chat-lead-gen' ); ?></h2>
			<p>
				<code>[wclg_chat_button]</code>
				<?php esc_html_e( 'inserisce il pulsante ovunque (accetta id="123" e label="Testo").', 'woo-chat-lead-gen' ); ?>
			</p>
		</div>
		<?php
	}

	/**
	 * Riga con importo in valuta.
	 *
	 * @param string $key         Chiave opzione.
	 * @param string $label       Etichetta.
	 * @param string $description Testo di aiuto.
	 * @param array  $settings    Valori correnti.
	 */
	private function number_row( $key, $label, $description, $settings ) {
		?>
		<tr>
			<th scope="row"><label for="wclg-<?php echo esc_attr( $key ); ?>"><?php echo esc_html( $label ); ?></label></th>
			<td>
				<input type="number" step="0.01" min="0" class="small-text" id="wclg-<?php echo esc_attr( $key ); ?>"
					name="<?php echo esc_attr( self::OPTION . '[' . $key . ']' ); ?>"
					value="<?php echo esc_attr( $settings[ $key ] ?? '0' ); ?>">
				<span><?php echo esc_html( get_woocommerce_currency_symbol() ); ?></span>
				<?php if ( $description ) : ?>
					<p class="description"><?php echo esc_html( $description ); ?></p>
				<?php endif; ?>
			</td>
		</tr>
		<?php
	}

	/**
	 * Riga checkbox della tabella impostazioni.
	 *
	 * @param string $key         Chiave opzione.
	 * @param string $label       Etichetta.
	 * @param string $description Testo di aiuto.
	 * @param array  $settings    Valori correnti.
	 */
	private function checkbox_row( $key, $label, $description, $settings ) {
		?>
		<tr>
			<th scope="row"><?php echo esc_html( $label ); ?></th>
			<td>
				<label>
					<input type="checkbox" name="<?php echo esc_attr( self::OPTION . '[' . $key . ']' ); ?>" value="yes" <?php checked( $settings[ $key ] ?? 'no', 'yes' ); ?>>
					<?php echo esc_html( $description ); ?>
				</label>
			</td>
		</tr>
		<?php
	}
}
