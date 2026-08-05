<?php
/**
 * Costruzione del messaggio precompilato e dell'URL di chat.
 *
 * Questa classe è l'unica fonte di verità del formato messaggio: il JS del
 * frontend replica la stessa logica per aggiornare il link quando l'utente
 * cambia taglia (vedi assets/js/wclg-frontend.js).
 *
 * @package WooChatLeadGen
 */

defined( 'ABSPATH' ) || exit;

class WCLG_Message {

	const WHATSAPP_ENDPOINT = 'https://api.whatsapp.com/send';
	const TELEGRAM_ENDPOINT = 'https://t.me/share/url';

	/**
	 * Segnaposto sostituibili nel template.
	 *
	 * @param WC_Product $product   Prodotto (semplice o variabile).
	 * @param array      $overrides Valori sovrascritti (variant, price, qty, sku...).
	 * @return array<string,string>
	 */
	public static function build_vars( $product, $overrides = array() ) {
		$vars = array(
			'product' => '',
			'price'   => '',
			'variant' => '',
			'sku'     => '',
			'qty'     => '',
			'url'     => '',
			'shop'    => get_bloginfo( 'name' ),
		);

		if ( $product instanceof WC_Product ) {
			$vars['product'] = $product->get_name();
			$vars['sku']     = $product->get_sku();
			$vars['url']     = $product->get_permalink();
			$vars['price']   = WCLG_Settings::is( 'hide_price' ) ? '' : self::format_price( $product );
		}

		$vars = array_merge( $vars, array_intersect_key( $overrides, $vars ) );

		/**
		 * Filtra i segnaposto del messaggio (es. per aggiungerne di custom).
		 *
		 * @param array      $vars    Segnaposto risolti.
		 * @param WC_Product $product Prodotto corrente.
		 */
		return apply_filters( 'wclg_message_vars', array_map( 'strval', $vars ), $product );
	}

	/**
	 * Prezzo leggibile ("€ 59,90"), senza HTML né entità.
	 *
	 * @param WC_Product $product Prodotto.
	 * @return string
	 */
	public static function format_price( $product ) {
		$price = wc_get_price_to_display( $product );
		if ( '' === $price || null === $price ) {
			return '';
		}
		return self::plain_text( wc_price( $price ) );
	}

	/**
	 * Rimuove tag e decodifica le entità HTML (&euro; -> €).
	 *
	 * @param string $html Frammento HTML.
	 * @return string
	 */
	public static function plain_text( $html ) {
		$text = html_entity_decode( wp_strip_all_tags( (string) $html ), ENT_QUOTES, 'UTF-8' );
		// wc_price() usa lo spazio unificatore: in chat conviene uno spazio normale.
		$text = str_replace( "\xc2\xa0", ' ', $text );
		return trim( preg_replace( '/\s+/u', ' ', $text ) );
	}

	/**
	 * Applica i segnaposto al template.
	 *
	 * Una riga che contiene solo segnaposto vuoti viene eliminata: così
	 * "Taglia: {variant}" sparisce sui prodotti senza varianti invece di
	 * lasciare un'etichetta orfana nel messaggio.
	 *
	 * @param string $template Template con segnaposto.
	 * @param array  $vars     Valori.
	 * @return string
	 */
	public static function render_template( $template, $vars ) {
		$lines  = preg_split( '/\r\n|\r|\n/', (string) $template );
		$output = array();

		foreach ( $lines as $line ) {
			if ( preg_match_all( '/\{([a-z_]+)\}/', $line, $matches ) ) {
				$filled = '';
				foreach ( $matches[1] as $key ) {
					$filled .= isset( $vars[ $key ] ) ? trim( $vars[ $key ] ) : '';
				}
				if ( '' === $filled ) {
					continue;
				}
			}
			$replacements = array();
			foreach ( $vars as $key => $value ) {
				$replacements[ '{' . $key . '}' ] = $value;
			}
			$output[] = strtr( $line, $replacements );
		}

		// Massimo una riga vuota consecutiva.
		$message = preg_replace( "/\n{3,}/", "\n\n", implode( "\n", $output ) );
		return trim( $message );
	}

	/**
	 * Messaggio finale per un prodotto.
	 *
	 * @param WC_Product $product   Prodotto.
	 * @param array      $overrides Valori sovrascritti.
	 * @return string
	 */
	public static function build_message( $product, $overrides = array() ) {
		$message = self::render_template(
			WCLG_Settings::get( 'message_template' ),
			self::build_vars( $product, $overrides )
		);

		/**
		 * Filtra il messaggio completo prima dell'encoding.
		 *
		 * @param string     $message Messaggio in chiaro.
		 * @param WC_Product $product Prodotto corrente.
		 */
		return apply_filters( 'wclg_message_text', $message, $product );
	}

	/**
	 * URL della chat con testo precompilato e correttamente URL-encoded.
	 *
	 * WhatsApp: https://api.whatsapp.com/send?phone=39...&text=...%0A...
	 * `rawurlencode` (RFC 3986) codifica gli a capo come %0A e gli spazi come
	 * %20: `urlencode` userebbe "+", che WhatsApp mostrerebbe letteralmente.
	 *
	 * @param string $message Messaggio in chiaro.
	 * @return string URL assoluto, oppure stringa vuota se il canale non è configurato.
	 */
	public static function build_url( $message ) {
		$channel = WCLG_Settings::get( 'channel' );
		$message = (string) $message;

		if ( 'telegram' === $channel ) {
			$user = WCLG_Settings::get( 'telegram_user' );
			if ( '' === $user ) {
				return '';
			}
			// L'endpoint /share richiede un url: usiamo quello del sito e mettiamo tutto in text.
			$url = self::TELEGRAM_ENDPOINT
				. '?url=' . rawurlencode( home_url( '/' ) )
				. '&text=' . rawurlencode( $message );
		} else {
			$phone = preg_replace( '/[^0-9]/', '', WCLG_Settings::get( 'phone' ) );
			if ( '' === $phone ) {
				return '';
			}
			$url = self::WHATSAPP_ENDPOINT
				. '?phone=' . rawurlencode( $phone )
				. '&text=' . rawurlencode( $message );
		}

		/**
		 * Filtra l'URL finale della chat.
		 *
		 * @param string $url     URL generato.
		 * @param string $message Messaggio in chiaro.
		 * @param string $channel Canale attivo.
		 */
		return apply_filters( 'wclg_chat_url', $url, $message, $channel );
	}

	/**
	 * Scorciatoia: prodotto -> URL chat pronto per l'attributo href.
	 *
	 * @param WC_Product $product   Prodotto.
	 * @param array      $overrides Valori sovrascritti.
	 * @return string
	 */
	public static function product_url( $product, $overrides = array() ) {
		return self::build_url( self::build_message( $product, $overrides ) );
	}
}
