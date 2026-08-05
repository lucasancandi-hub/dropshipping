<?php
/**
 * Stima della spedizione.
 *
 * Non è un calcolo fiscale: è una stima da mostrare nel riepilogo e da
 * scrivere nel messaggio, che verrà confermata in chat. Per questo la
 * spedizione può sempre valere "da concordare".
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Shipping {

	/**
	 * Stima per il carrello corrente.
	 *
	 * @return array{amount: float|null, label: string, on_request: bool, free: bool}
	 */
	public static function estimate() {
		$on_request = array(
			'amount'     => null,
			'label'      => __( 'Da concordare in chat', 'woo-chat-lead-gen' ),
			'on_request' => true,
			'free'       => false,
		);

		if ( ! function_exists( 'WC' ) || ! WC()->cart || WC()->cart->is_empty() ) {
			return $on_request;
		}

		$mode = WCLG_Settings::get( 'shipping_mode', 'flat' );
		if ( 'none' === $mode ) {
			return $on_request;
		}

		// Soglia di spedizione gratuita sul subtotale merce.
		$free_over = (float) WCLG_Settings::get( 'shipping_free_over', 0 );
		$subtotal  = (float) WC()->cart->get_displayed_subtotal();
		if ( $free_over > 0 && $subtotal >= $free_over ) {
			return self::result( 0.0, true );
		}

		$base = (float) WCLG_Settings::get( 'shipping_base', 0 );
		$rate = (float) WCLG_Settings::get( 'shipping_rate', 0 );

		switch ( $mode ) {
			case 'quantity':
				$amount = $base + $rate * self::cart_quantity();
				break;

			case 'weight':
				$amount = $base + $rate * self::cart_weight();
				break;

			case 'woo':
				// Usa le spedizioni native se una tariffa è già stata scelta.
				$calculated = (float) WC()->cart->get_shipping_total();
				if ( $calculated > 0 ) {
					$amount = $calculated;
					break;
				}
				$amount = (float) WCLG_Settings::get( 'shipping_flat', 0 );
				break;

			case 'flat':
			default:
				$amount = (float) WCLG_Settings::get( 'shipping_flat', 0 );
				break;
		}

		/**
		 * Filtra l'importo stimato di spedizione.
		 *
		 * @param float  $amount Importo.
		 * @param string $mode   Modalità di calcolo.
		 */
		$amount = (float) apply_filters( 'wclg_shipping_estimate', max( 0, $amount ), $mode );

		return self::result( $amount, 0.0 === $amount );
	}

	/**
	 * Confeziona il risultato con l'etichetta già formattata.
	 *
	 * @param float $amount Importo.
	 * @param bool  $free   Se è gratuita.
	 * @return array
	 */
	private static function result( $amount, $free ) {
		return array(
			'amount'     => (float) $amount,
			'label'      => $free
				? __( 'Gratuita', 'woo-chat-lead-gen' )
				: WCLG_Message::plain_text( wc_price( $amount ) ),
			'on_request' => false,
			'free'       => (bool) $free,
		);
	}

	/**
	 * @return int Numero totale di pezzi nel carrello.
	 */
	private static function cart_quantity() {
		return (int) WC()->cart->get_cart_contents_count();
	}

	/**
	 * @return float Peso del carrello convertito in kg.
	 */
	private static function cart_weight() {
		$weight = (float) WC()->cart->get_cart_contents_weight();
		return (float) wc_get_weight( $weight, 'kg' );
	}

	/**
	 * Descrizione della regola attiva, per l'interfaccia.
	 *
	 * @return string
	 */
	public static function describe() {
		$mode = WCLG_Settings::get( 'shipping_mode', 'flat' );
		$rate = WCLG_Message::plain_text( wc_price( (float) WCLG_Settings::get( 'shipping_rate', 0 ) ) );

		switch ( $mode ) {
			case 'quantity':
				/* translators: %s: tariffa per articolo. */
				return sprintf( __( 'Stima: %s per articolo', 'woo-chat-lead-gen' ), $rate );
			case 'weight':
				/* translators: %s: tariffa al kg. */
				return sprintf( __( 'Stima: %s al kg', 'woo-chat-lead-gen' ), $rate );
			case 'none':
				return __( 'Definita in chat', 'woo-chat-lead-gen' );
			default:
				return __( 'Tariffa fissa', 'woo-chat-lead-gen' );
		}
	}
}
