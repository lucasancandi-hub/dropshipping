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
			'enabled'            => 'yes',
			'channel'            => 'whatsapp',
			'phone'              => '',
			'telegram_user'      => '',
			'button_label'       => __( 'Ordina via WhatsApp', 'woo-chat-lead-gen' ),
			'loop_button_label'  => __( 'Ordina in chat', 'woo-chat-lead-gen' ),
			'loop_button_action' => 'product',
			'message_template'   => self::default_template(),
			'disable_cart'       => 'yes',
			'hide_price'         => 'no',
			'show_quantity'      => 'yes',
			'sticky_mobile'      => 'yes',
			'load_css'           => 'yes',
			'new_tab'            => 'yes',
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
		$checkboxes = array( 'enabled', 'disable_cart', 'hide_price', 'show_quantity', 'sticky_mobile', 'load_css', 'new_tab' );

		foreach ( $checkboxes as $key ) {
			$clean[ $key ] = ! empty( $input[ $key ] ) ? 'yes' : 'no';
		}

		$clean['channel'] = in_array( $input['channel'] ?? '', array( 'whatsapp', 'telegram' ), true )
			? $input['channel']
			: $defaults['channel'];

		$clean['loop_button_action'] = in_array( $input['loop_button_action'] ?? '', array( 'product', 'chat' ), true )
			? $input['loop_button_action']
			: $defaults['loop_button_action'];

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
					$this->checkbox_row( 'enabled', __( 'Attiva modalità catalogo', 'woo-chat-lead-gen' ), __( 'Sostituisci "Aggiungi al carrello" con il pulsante chat.', 'woo-chat-lead-gen' ), $settings );
					?>
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
						<th scope="row"><label for="wclg-label"><?php esc_html_e( 'Etichetta pulsante (scheda prodotto)', 'woo-chat-lead-gen' ); ?></label></th>
						<td><input type="text" class="regular-text" id="wclg-label" name="<?php echo esc_attr( self::OPTION ); ?>[button_label]" value="<?php echo esc_attr( $settings['button_label'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="wclg-loop-label"><?php esc_html_e( 'Etichetta pulsante (catalogo)', 'woo-chat-lead-gen' ); ?></label></th>
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
						<th scope="row"><label for="wclg-template"><?php esc_html_e( 'Messaggio precompilato', 'woo-chat-lead-gen' ); ?></label></th>
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
					$this->checkbox_row( 'disable_cart', __( 'Disattiva carrello e pagamenti', 'woo-chat-lead-gen' ), __( 'Blocca gli aggiunta-al-carrello, reindirizza carrello/checkout e rimuove i gateway di pagamento.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'show_quantity', __( 'Selettore quantità', 'woo-chat-lead-gen' ), __( 'Mostra il campo quantità accanto al pulsante chat.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'hide_price', __( 'Nascondi i prezzi', 'woo-chat-lead-gen' ), __( 'Utile per listini su richiesta.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'sticky_mobile', __( 'CTA fissa su mobile', 'woo-chat-lead-gen' ), __( 'Barra sempre visibile in fondo allo schermo nella scheda prodotto.', 'woo-chat-lead-gen' ), $settings );
					$this->checkbox_row( 'new_tab', __( 'Apri la chat in una nuova scheda', 'woo-chat-lead-gen' ), '', $settings );
					$this->checkbox_row( 'load_css', __( 'Carica il CSS del plugin', 'woo-chat-lead-gen' ), __( 'Disattiva se preferisci gestire lo stile dal tema.', 'woo-chat-lead-gen' ), $settings );
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
