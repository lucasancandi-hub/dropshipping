<?php
/**
 * Plugin Name:       Woo Chat Lead Gen
 * Plugin URI:        https://github.com/lucasancandi-hub/dropshipping
 * Description:       Trasforma WooCommerce in un catalogo per lead generation: disattiva carrello e pagamenti e sostituisce "Aggiungi al carrello" con un CTA "Ordina via WhatsApp" che precompila il messaggio con prodotto, prezzo e taglia selezionata.
 * Version:           1.0.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            Luca Sancandi
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       woo-chat-lead-gen
 * Domain Path:       /languages
 * WC requires at least: 7.0
 * WC tested up to:   9.9
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

define( 'WCLG_VERSION', '1.0.0' );
define( 'WCLG_FILE', __FILE__ );
define( 'WCLG_PATH', plugin_dir_path( __FILE__ ) );
define( 'WCLG_URL', plugin_dir_url( __FILE__ ) );

/**
 * Bootstrap del plugin.
 *
 * Carica i moduli solo se WooCommerce è attivo: senza WooCommerce gli hook
 * non esistono e il sito andrebbe in fatal error.
 */
final class WCLG_Plugin {

	/**
	 * Istanza singleton.
	 *
	 * @var WCLG_Plugin|null
	 */
	private static $instance = null;

	/**
	 * @return WCLG_Plugin
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'plugins_loaded', array( $this, 'boot' ) );
		add_action( 'before_woocommerce_init', array( $this, 'declare_compatibility' ) );
	}

	/**
	 * Dichiara la compatibilità con HPOS (High-Performance Order Storage).
	 */
	public function declare_compatibility() {
		if ( class_exists( \Automattic\WooCommerce\Utilities\FeaturesUtil::class ) ) {
			\Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility( 'custom_order_tables', WCLG_FILE, true );
		}
	}

	/**
	 * Carica le dipendenze e istanzia i moduli.
	 */
	public function boot() {
		if ( ! class_exists( 'WooCommerce' ) ) {
			add_action( 'admin_notices', array( $this, 'missing_woocommerce_notice' ) );
			return;
		}

		require_once WCLG_PATH . 'includes/class-wclg-settings.php';
		require_once WCLG_PATH . 'includes/class-wclg-message.php';
		require_once WCLG_PATH . 'includes/class-wclg-catalog-mode.php';
		require_once WCLG_PATH . 'includes/class-wclg-frontend.php';

		load_plugin_textdomain( 'woo-chat-lead-gen', false, dirname( plugin_basename( WCLG_FILE ) ) . '/languages' );

		WCLG_Settings::instance();

		if ( ! WCLG_Settings::is_enabled() ) {
			return;
		}

		WCLG_Catalog_Mode::instance();
		WCLG_Frontend::instance();
	}

	public function missing_woocommerce_notice() {
		printf(
			'<div class="notice notice-error"><p>%s</p></div>',
			esc_html__( 'Woo Chat Lead Gen richiede WooCommerce attivo.', 'woo-chat-lead-gen' )
		);
	}
}

WCLG_Plugin::instance();
