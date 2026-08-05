<?php
/**
 * ============================================================================
 * WooCommerce -> Lead generation via chat (versione compatta per functions.php)
 * ============================================================================
 *
 * Alternativa "quick & dirty" al plugin in wp-content/plugins/woo-chat-lead-gen.
 * Copia tutto ciò che segue (senza il tag <?php iniziale se il file ne ha già
 * uno) in fondo al functions.php del tema CHILD.
 *
 * Cosa fa:
 *  1. blocca carrello, checkout e gateway di pagamento;
 *  2. rimuove i pulsanti "Aggiungi al carrello";
 *  3. stampa un CTA "Ordina via WhatsApp" con messaggio precompilato che
 *     include titolo, prezzo, taglia selezionata e link del prodotto.
 *
 * Configurazione: le due costanti qui sotto.
 *
 * @package WooChatLeadGen\Snippet
 */

defined( 'ABSPATH' ) || exit;

/** Numero WhatsApp in formato internazionale, solo cifre. */
define( 'MYSHOP_WA_PHONE', '393401234567' );

/** Etichetta del pulsante. */
define( 'MYSHOP_WA_LABEL', 'Ordina via WhatsApp' );

/* -------------------------------------------------------------------------- *
 * 1. Modalità catalogo: niente carrello, niente pagamenti
 * -------------------------------------------------------------------------- */

add_filter( 'woocommerce_add_to_cart_validation', '__return_false', 99 );
add_filter( 'woocommerce_available_payment_gateways', '__return_empty_array', 99 );
add_filter( 'woocommerce_widget_cart_is_hidden', '__return_true', 99 );

add_action(
	'template_redirect',
	function () {
		if ( ! is_admin() && function_exists( 'is_cart' ) && ( is_cart() || is_checkout() ) ) {
			wp_safe_redirect( wc_get_page_permalink( 'shop' ) );
			exit;
		}
	}
);

/* -------------------------------------------------------------------------- *
 * 2. Messaggio precompilato
 * -------------------------------------------------------------------------- */

/**
 * Costruisce l'URL WhatsApp con il testo codificato (RFC 3986).
 *
 * `rawurlencode` traduce gli a capo in %0A e gli spazi in %20: `urlencode`
 * userebbe "+", che WhatsApp mostrerebbe letteralmente nel messaggio.
 *
 * @param WC_Product $product Prodotto corrente.
 * @return string
 */
function myshop_wa_url( $product ) {
	$price = wc_price( wc_get_price_to_display( $product ) );
	$price = trim( html_entity_decode( wp_strip_all_tags( $price ), ENT_QUOTES, 'UTF-8' ) );

	$lines = array(
		'Ciao! 👋 Vorrei ordinare questo articolo:',
		'',
		'*' . $product->get_name() . '*',
		'Prezzo: ' . $price,
	);

	if ( $product->get_sku() ) {
		$lines[] = 'Codice: ' . $product->get_sku();
	}

	$lines[] = '';
	$lines[] = $product->get_permalink();

	return 'https://api.whatsapp.com/send?phone=' . rawurlencode( MYSHOP_WA_PHONE )
		. '&text=' . rawurlencode( implode( "\n", $lines ) );
}

/**
 * Markup del pulsante.
 *
 * @param WC_Product $product Prodotto.
 * @param string     $context single|loop.
 * @return string
 */
function myshop_wa_button( $product, $context = 'single' ) {
	return sprintf(
		'<div class="wclg-cta" data-wa-product="%1$s" data-wa-price="%2$s" data-wa-url="%3$s" data-wa-phone="%4$s">
			<a href="%5$s" class="button wclg-button wclg-button--%6$s" target="_blank" rel="noopener nofollow">%7$s</a>
		</div>',
		esc_attr( $product->get_name() ),
		esc_attr( trim( html_entity_decode( wp_strip_all_tags( wc_price( wc_get_price_to_display( $product ) ) ), ENT_QUOTES, 'UTF-8' ) ) ),
		esc_attr( $product->get_permalink() ),
		esc_attr( MYSHOP_WA_PHONE ),
		esc_url( myshop_wa_url( $product ) ),
		esc_attr( $context ),
		esc_html( MYSHOP_WA_LABEL )
	);
}

/* -------------------------------------------------------------------------- *
 * 3. Sostituzione dei pulsanti nativi
 * -------------------------------------------------------------------------- */

// 3a. Griglia catalogo: il link porta alla scheda, dove si sceglie la taglia.
add_filter(
	'woocommerce_loop_add_to_cart_link',
	function ( $html, $product ) {
		return sprintf(
			'<a href="%s" class="button wclg-button wclg-button--loop">%s</a>',
			esc_url( $product->get_permalink() ),
			esc_html( 'Ordina in chat' )
		);
	},
	99,
	2
);

// 3b. Scheda prodotto.
add_action(
	'wp',
	function () {
		if ( ! is_product() ) {
			return;
		}

		$product = wc_get_product( get_queried_object_id() );
		if ( ! $product ) {
			return;
		}

		if ( $product->is_type( 'variable' ) ) {
			// Il form resta (serve il menu taglie): togliamo quantità e bottone.
			add_action( 'woocommerce_before_add_to_cart_button', function () { ob_start(); }, -9999 );
			add_action(
				'woocommerce_after_add_to_cart_button',
				function () {
					if ( ob_get_level() > 0 ) {
						ob_end_clean();
					}
				},
				9999
			);
			add_action(
				'woocommerce_after_add_to_cart_form',
				function () {
					global $product;
					echo myshop_wa_button( $product ); // phpcs:ignore WordPress.Security.EscapeOutput
				},
				5
			);
		} else {
			remove_action( 'woocommerce_single_product_summary', 'woocommerce_template_single_add_to_cart', 30 );
			add_action(
				'woocommerce_single_product_summary',
				function () {
					global $product;
					echo myshop_wa_button( $product ); // phpcs:ignore WordPress.Security.EscapeOutput
				},
				30
			);
		}
	}
);

/* -------------------------------------------------------------------------- *
 * 4. JS inline: aggiorna il link con la taglia scelta
 * -------------------------------------------------------------------------- */

add_action(
	'wp_footer',
	function () {
		if ( ! function_exists( 'is_product' ) || ! is_product() ) {
			return;
		}
		?>
		<script>
		( function () {
			var cta = document.querySelector( '.wclg-cta[data-wa-phone]' );
			var form = document.querySelector( 'form.variations_form' );
			if ( ! cta || ! form ) {
				return;
			}

			var link = cta.querySelector( 'a' );

			function selectedAttributes() {
				var values = [];
				form.querySelectorAll( 'select[name^="attribute_"]' ).forEach( function ( select ) {
					if ( select.value ) {
						var option = select.options[ select.selectedIndex ];
						values.push( ( option ? option.textContent : select.value ).trim() );
					}
				} );
				return values.join( ' / ' );
			}

			function refresh() {
				var variant = selectedAttributes();
				var lines = [
					'Ciao! 👋 Vorrei ordinare questo articolo:',
					'',
					'*' + cta.dataset.waProduct + '*'
				];

				if ( variant ) {
					lines.push( 'Taglia: ' + variant );
				}

				lines.push( 'Prezzo: ' + cta.dataset.waPrice, '', cta.dataset.waUrl );

				link.href = 'https://api.whatsapp.com/send?phone=' + cta.dataset.waPhone +
					'&text=' + encodeURIComponent( lines.join( '\n' ) );
			}

			form.addEventListener( 'change', refresh );
			refresh();
		} )();
		</script>
		<?php
	},
	99
);
