<?php
/**
 * Prezzo da concordare in chat.
 *
 * Un prodotto è "su richiesta" se l'admin ha spuntato la casella dedicata
 * oppure se semplicemente non ha un prezzo. WooCommerce considera non
 * acquistabile un prodotto senza prezzo: qui lo rendiamo acquistabile lo
 * stesso, perché nel flusso chat il carrello è una lista di richiesta, non
 * una transazione.
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Price {

	const META = '_wclg_price_on_request';

	/**
	 * @var WCLG_Price|null
	 */
	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		// Frontend.
		add_filter( 'woocommerce_get_price_html', array( $this, 'price_html' ), 20, 2 );
		add_filter( 'woocommerce_is_purchasable', array( $this, 'is_purchasable' ), 20, 2 );
		add_filter( 'woocommerce_variation_is_purchasable', array( $this, 'is_purchasable' ), 20, 2 );
		add_filter( 'woocommerce_cart_item_price', array( $this, 'cart_item_price' ), 20, 2 );
		add_filter( 'woocommerce_cart_item_subtotal', array( $this, 'cart_item_price' ), 20, 2 );

		// Admin: casella su prodotto e su singola variazione.
		add_action( 'woocommerce_product_options_pricing', array( $this, 'render_product_field' ) );
		add_action( 'woocommerce_process_product_meta', array( $this, 'save_product_field' ) );
		add_action( 'woocommerce_variation_options_pricing', array( $this, 'render_variation_field' ), 10, 3 );
		add_action( 'woocommerce_save_product_variation', array( $this, 'save_variation_field' ), 10, 2 );
	}

	/* --------------------------------------------------------------------- *
	 * Stato
	 * --------------------------------------------------------------------- */

	/**
	 * Il prezzo di questo prodotto va concordato in chat?
	 *
	 * Per le variazioni vale prima il flag della variazione, poi quello del
	 * prodotto padre.
	 *
	 * @param WC_Product|int|null $product Prodotto o ID.
	 * @return bool
	 */
	public static function is_on_request( $product ) {
		if ( is_numeric( $product ) ) {
			$product = wc_get_product( $product );
		}
		if ( ! $product instanceof WC_Product ) {
			return false;
		}

		$on_request = 'yes' === $product->get_meta( self::META );

		if ( ! $on_request && $product->is_type( 'variation' ) ) {
			$parent = wc_get_product( $product->get_parent_id() );
			$on_request = $parent instanceof WC_Product && 'yes' === $parent->get_meta( self::META );
		}

		// Nessun prezzo impostato: di fatto è un prezzo da concordare.
		if ( ! $on_request && '' === (string) $product->get_price() ) {
			$on_request = true;
		}

		/**
		 * Filtra la valutazione "prezzo su richiesta".
		 *
		 * @param bool       $on_request Esito.
		 * @param WC_Product $product    Prodotto.
		 */
		return (bool) apply_filters( 'wclg_is_price_on_request', $on_request, $product );
	}

	/**
	 * @return string Etichetta mostrata al posto del prezzo.
	 */
	public static function label() {
		return WCLG_Settings::get( 'price_request_label', __( 'Prezzo da concordare in chat', 'woo-chat-lead-gen' ) );
	}

	/* --------------------------------------------------------------------- *
	 * Frontend
	 * --------------------------------------------------------------------- */

	/**
	 * @param string     $html    HTML del prezzo.
	 * @param WC_Product $product Prodotto.
	 * @return string
	 */
	public function price_html( $html, $product ) {
		if ( ! self::is_on_request( $product ) ) {
			return $html;
		}
		return '<span class="wclg-price-request">' . esc_html( self::label() ) . '</span>';
	}

	/**
	 * Rende acquistabile (= aggiungibile alla lista) anche chi non ha prezzo.
	 *
	 * @param bool       $purchasable Esito originale.
	 * @param WC_Product $product     Prodotto.
	 * @return bool
	 */
	public function is_purchasable( $purchasable, $product ) {
		if ( $purchasable || 'cart' !== WCLG_Settings::get( 'order_flow' ) ) {
			return $purchasable;
		}
		return self::is_on_request( $product );
	}

	/**
	 * @param string $html      Prezzo/subtotale di riga.
	 * @param array  $cart_item Riga del carrello.
	 * @return string
	 */
	public function cart_item_price( $html, $cart_item ) {
		$product = isset( $cart_item['data'] ) ? $cart_item['data'] : null;
		if ( ! self::is_on_request( $product ) ) {
			return $html;
		}
		return '<span class="wclg-price-request">' . esc_html( self::label() ) . '</span>';
	}

	/* --------------------------------------------------------------------- *
	 * Admin
	 * --------------------------------------------------------------------- */

	public function render_product_field() {
		woocommerce_wp_checkbox(
			array(
				'id'          => self::META,
				'label'       => __( 'Prezzo da concordare', 'woo-chat-lead-gen' ),
				'description' => __( 'Nasconde il prezzo e lo segnala come da concordare in chat.', 'woo-chat-lead-gen' ),
			)
		);
	}

	/**
	 * @param int $post_id ID prodotto. Il nonce è già verificato da WooCommerce.
	 */
	public function save_product_field( $post_id ) {
		$product = wc_get_product( $post_id );
		if ( ! $product ) {
			return;
		}
		$product->update_meta_data( self::META, isset( $_POST[ self::META ] ) ? 'yes' : 'no' ); // phpcs:ignore WordPress.Security.NonceVerification.Missing
		$product->save();
	}

	/**
	 * @param int     $loop           Indice della variazione nel form.
	 * @param array   $variation_data Dati (legacy).
	 * @param WP_Post $variation      Post della variazione.
	 */
	public function render_variation_field( $loop, $variation_data, $variation ) {
		woocommerce_wp_checkbox(
			array(
				'id'            => self::META . '[' . $loop . ']',
				'label'         => __( 'Prezzo da concordare', 'woo-chat-lead-gen' ),
				'value'         => get_post_meta( $variation->ID, self::META, true ),
				'wrapper_class' => 'form-row form-row-full',
			)
		);
	}

	/**
	 * @param int $variation_id ID variazione.
	 * @param int $loop         Indice nel form.
	 */
	public function save_variation_field( $variation_id, $loop ) {
		// phpcs:ignore WordPress.Security.NonceVerification.Missing -- verificato da WooCommerce.
		$value = isset( $_POST[ self::META ][ $loop ] ) ? 'yes' : 'no';
		update_post_meta( $variation_id, self::META, $value );
	}
}
