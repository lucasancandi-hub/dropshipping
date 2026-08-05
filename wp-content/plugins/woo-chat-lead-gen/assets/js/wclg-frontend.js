/**
 * Woo Chat Lead Gen - frontend.
 *
 * Tiene il link della chat allineato a ciò che l'utente ha scelto:
 * variante (taglia), prezzo della variante e quantità.
 * La logica del template replica quella di WCLG_Message::render_template().
 */
( function ( $ ) {
	'use strict';

	var SELECTOR = '.wclg-cta';

	/* --------------------------------------------------------------------- *
	 * Utility
	 * --------------------------------------------------------------------- */

	/**
	 * Formatta un numero secondo le impostazioni valuta di WooCommerce.
	 *
	 * @param {number|string} value  Prezzo.
	 * @param {Object}        format symbol/decimals/decimalSep/thousandSep/format.
	 * @return {string} Prezzo formattato, stringa vuota se non numerico.
	 */
	function formatPrice( value, format ) {
		var amount = parseFloat( value );
		if ( isNaN( amount ) ) {
			return '';
		}

		var parts = amount.toFixed( format.decimals ).split( '.' );
		parts[ 0 ] = parts[ 0 ].replace( /\B(?=(\d{3})+(?!\d))/g, format.thousandSep );

		var number = parts.join( format.decimalSep );

		return ( format.format || '%1$s%2$s' )
			.replace( '%1$s', format.symbol )
			.replace( '%2$s', number )
			.replace( /&nbsp;/g, ' ' )
			.trim();
	}

	/**
	 * Applica i segnaposto al template scartando le righe rimaste vuote.
	 *
	 * @param {string} template Template con {segnaposto}.
	 * @param {Object} vars     Valori.
	 * @return {string} Messaggio in chiaro.
	 */
	function renderTemplate( template, vars ) {
		var lines = String( template ).split( /\r\n|\r|\n/ );
		var output = [];

		lines.forEach( function ( line ) {
			var placeholders = line.match( /\{([a-z_]+)\}/g );

			if ( placeholders ) {
				var filled = placeholders.reduce( function ( acc, token ) {
					var key = token.slice( 1, -1 );
					return acc + ( vars[ key ] ? String( vars[ key ] ).trim() : '' );
				}, '' );

				if ( '' === filled ) {
					return; // Riga con soli segnaposto vuoti: si elimina.
				}
			}

			output.push(
				line.replace( /\{([a-z_]+)\}/g, function ( match, key ) {
					return undefined !== vars[ key ] && null !== vars[ key ] ? vars[ key ] : '';
				} )
			);
		} );

		return output.join( '\n' ).replace( /\n{3,}/g, '\n\n' ).trim();
	}

	/* --------------------------------------------------------------------- *
	 * CTA
	 * --------------------------------------------------------------------- */

	/**
	 * @param {HTMLElement} root Contenitore .wclg-cta
	 * @constructor
	 */
	function ChatCta( root ) {
		this.root = root;

		try {
			this.config = JSON.parse( root.getAttribute( 'data-wclg' ) || '{}' );
		} catch ( error ) {
			return;
		}
		if ( ! this.config.prefix ) {
			return;
		}

		this.link = root.querySelector( '[data-wclg-action="chat"]' );
		this.qtyInput = root.querySelector( '.wclg-qty__input' );
		this.form = this.findVariationsForm();
		this.state = { variant: '', price: this.config.vars.price || '', sku: this.config.vars.sku || '' };

		this.bindQuantity();
		this.bindVariations();
		this.bindTracking();
		this.update();

		root.classList.add( 'wclg-cta--ready' );
	}

	/**
	 * Il form varianti è fuori dal nostro contenitore: lo cerchiamo nel
	 * riepilogo prodotto più vicino.
	 *
	 * @return {HTMLFormElement|null}
	 */
	ChatCta.prototype.findVariationsForm = function () {
		var scope = this.root.closest( '.product, .summary, .entry-summary' ) || document;
		return scope.querySelector( 'form.variations_form' ) || document.querySelector( 'form.variations_form' );
	};

	/**
	 * Quantità: pulsanti +/- e input manuale.
	 */
	ChatCta.prototype.bindQuantity = function () {
		var self = this;
		if ( ! this.qtyInput ) {
			return;
		}

		this.root.querySelectorAll( '[data-wclg-step]' ).forEach( function ( button ) {
			button.addEventListener( 'click', function () {
				var step = parseInt( button.getAttribute( 'data-wclg-step' ), 10 ) || 1;
				var next = ( parseInt( self.qtyInput.value, 10 ) || 1 ) + step;
				self.qtyInput.value = Math.max( 1, next );
				self.update();
			} );
		} );

		this.qtyInput.addEventListener( 'change', function () {
			self.qtyInput.value = Math.max( 1, parseInt( self.qtyInput.value, 10 ) || 1 );
			self.update();
		} );
	};

	/**
	 * Si aggancia agli eventi di wc-add-to-cart-variation.js.
	 */
	ChatCta.prototype.bindVariations = function () {
		var self = this;
		if ( ! this.form || ! $ ) {
			return;
		}

		$( this.form )
			.on( 'found_variation.wclg', function ( event, variation ) {
				self.state.variant = self.readSelectedAttributes();
				self.state.sku = variation && variation.sku ? variation.sku : self.config.vars.sku;
				self.state.price =
					! self.config.hidePrice && variation && undefined !== variation.display_price
						? formatPrice( variation.display_price, self.config.priceFormat )
						: self.config.vars.price;
				self.update();
			} )
			.on( 'reset_data.wclg hide_variation.wclg', function () {
				self.state.variant = self.readSelectedAttributes();
				self.state.price = self.config.vars.price;
				self.state.sku = self.config.vars.sku;
				self.update();
			} );

		// Anche il solo cambio di select (senza variante completa) va riflesso.
		this.form.addEventListener( 'change', function () {
			self.state.variant = self.readSelectedAttributes();
			self.update();
		} );
	};

	/**
	 * Etichette leggibili delle opzioni scelte: "M" oppure "M / Nero".
	 *
	 * @return {string}
	 */
	ChatCta.prototype.readSelectedAttributes = function () {
		if ( ! this.form ) {
			return '';
		}

		var values = [];
		this.form.querySelectorAll( 'select[name^="attribute_"]' ).forEach( function ( select ) {
			if ( ! select.value ) {
				return;
			}
			var option = select.options[ select.selectedIndex ];
			values.push( ( option ? option.textContent : select.value ).trim() );
		} );

		return values.join( ' / ' );
	};

	/**
	 * Ricalcola href e stato del pulsante.
	 */
	ChatCta.prototype.update = function () {
		if ( ! this.link ) {
			return;
		}

		var vars = {};
		Object.keys( this.config.vars ).forEach( function ( key ) {
			vars[ key ] = this.config.vars[ key ];
		}, this );

		vars.variant = this.state.variant;
		vars.price = this.state.price;
		vars.sku = this.state.sku;
		vars.qty = this.qtyInput && parseInt( this.qtyInput.value, 10 ) > 1 ? this.qtyInput.value : '';

		this.message = renderTemplate( this.config.template, vars );
		this.link.href = this.config.prefix + encodeURIComponent( this.message );

		document.dispatchEvent(
			new CustomEvent( 'wclg:updated', { detail: { root: this.root, message: this.message } } )
		);
	};

	/**
	 * Evento per analytics (GA4 / GTM) sul click.
	 */
	ChatCta.prototype.bindTracking = function () {
		var self = this;
		if ( ! this.link ) {
			return;
		}

		this.link.addEventListener( 'click', function () {
			var payload = {
				event: 'wclg_chat_click',
				product: self.config.vars.product,
				variant: self.state.variant,
				price: self.state.price
			};

			window.dataLayer = window.dataLayer || [];
			window.dataLayer.push( payload );
			document.dispatchEvent( new CustomEvent( 'wclg:click', { detail: payload } ) );
		} );
	};

	/* --------------------------------------------------------------------- *
	 * Barra fissa mobile
	 * --------------------------------------------------------------------- */

	/**
	 * Mostra la barra quando il CTA principale esce dalla viewport e ne
	 * rispecchia il link (quindi anche la variante scelta).
	 */
	function initStickyBar() {
		var bar = document.querySelector( '[data-wclg-sticky]' );
		var cta = document.querySelector( SELECTOR + ' [data-wclg-action="chat"]' );
		if ( ! bar || ! cta ) {
			return;
		}

		var stickyLink = bar.querySelector( '[data-wclg-sticky-link]' );
		var sync = function () {
			stickyLink.href = cta.href;
			stickyLink.target = cta.target;
			stickyLink.rel = cta.rel;
		};

		sync();
		document.addEventListener( 'wclg:updated', sync );

		if ( ! ( 'IntersectionObserver' in window ) ) {
			bar.hidden = false;
			return;
		}

		new IntersectionObserver(
			function ( entries ) {
				bar.hidden = entries[ 0 ].isIntersecting;
			},
			{ threshold: 0 }
		).observe( cta );
	}

	/* --------------------------------------------------------------------- *
	 * Bootstrap
	 * --------------------------------------------------------------------- */

	function init() {
		document.querySelectorAll( SELECTOR ).forEach( function ( root ) {
			if ( ! root.wclgInstance ) {
				root.wclgInstance = new ChatCta( root );
			}
		} );
		initStickyBar();
	}

	if ( 'loading' === document.readyState ) {
		document.addEventListener( 'DOMContentLoaded', init );
	} else {
		init();
	}

	// Rende i pezzi riutilizzabili da codice del tema.
	window.WCLG = { renderTemplate: renderTemplate, formatPrice: formatPrice, init: init };
} )( window.jQuery );
