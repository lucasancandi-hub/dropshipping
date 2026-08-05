/**
 * Woo Chat Lead Gen - drawer carrello.
 *
 * Il contenuto del pannello è il mini carrello di WooCommerce dentro un
 * `div.widget_shopping_cart_content`: i frammenti AJAX nativi lo aggiornano
 * da soli dopo ogni aggiunta, quindi qui gestiamo solo apertura, chiusura e
 * stato del pulsante flottante.
 */
( function ( $ ) {
	'use strict';

	var drawer = null;
	var fab = null;
	var lastFocused = null;

	/* --------------------------------------------------------------------- *
	 * Apertura / chiusura
	 * --------------------------------------------------------------------- */

	function open() {
		if ( ! drawer ) {
			return;
		}

		lastFocused = document.activeElement;
		drawer.hidden = false;
		document.body.classList.add( 'wclg-drawer-open' );

		// Il focus entra nel pannello: chi naviga da tastiera non resta fuori.
		var closeButton = drawer.querySelector( '[data-wclg-drawer-close]:not(.wclg-drawer__backdrop)' );
		if ( closeButton ) {
			closeButton.focus();
		}

		document.dispatchEvent( new CustomEvent( 'wclg:drawer-open' ) );
	}

	function close() {
		if ( ! drawer || drawer.hidden ) {
			return;
		}

		drawer.hidden = true;
		document.body.classList.remove( 'wclg-drawer-open' );

		if ( lastFocused && document.contains( lastFocused ) ) {
			lastFocused.focus();
		}

		document.dispatchEvent( new CustomEvent( 'wclg:drawer-close' ) );
	}

	/**
	 * Mantiene il focus dentro il pannello finché è aperto.
	 *
	 * @param {KeyboardEvent} event Evento tastiera.
	 */
	function trapFocus( event ) {
		if ( 'Tab' !== event.key || ! drawer || drawer.hidden ) {
			return;
		}

		var focusables = drawer.querySelectorAll(
			'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'
		);
		if ( ! focusables.length ) {
			return;
		}

		var first = focusables[ 0 ];
		var last = focusables[ focusables.length - 1 ];

		if ( event.shiftKey && document.activeElement === first ) {
			event.preventDefault();
			last.focus();
		} else if ( ! event.shiftKey && document.activeElement === last ) {
			event.preventDefault();
			first.focus();
		}
	}

	/* --------------------------------------------------------------------- *
	 * Pulsante flottante
	 * --------------------------------------------------------------------- */

	/**
	 * Nasconde il FAB a carrello vuoto: niente icona inutile a schermo.
	 */
	function refreshFab() {
		if ( ! fab ) {
			return;
		}

		var counter = fab.querySelector( '[data-wclg-count]' );
		var count = counter ? parseInt( counter.textContent, 10 ) || 0 : 0;

		fab.classList.toggle( 'wclg-fab--empty', 0 === count );
		fab.setAttribute( 'aria-hidden', 0 === count ? 'true' : 'false' );

		if ( 0 === count ) {
			close();
		}
	}

	/* --------------------------------------------------------------------- *
	 * Bootstrap
	 * --------------------------------------------------------------------- */

	function init() {
		drawer = document.querySelector( '[data-wclg-drawer]' );
		fab = document.querySelector( '.wclg-fab' );

		if ( fab ) {
			fab.addEventListener( 'click', open );
		}

		document.addEventListener( 'click', function ( event ) {
			if ( event.target.closest( '[data-wclg-drawer-open]' ) ) {
				event.preventDefault();
				open();
			} else if ( event.target.closest( '[data-wclg-drawer-close]' ) ) {
				event.preventDefault();
				close();
			}
		} );

		document.addEventListener( 'keydown', function ( event ) {
			if ( 'Escape' === event.key ) {
				close();
			}
			trapFocus( event );
		} );

		refreshFab();

		if ( ! $ ) {
			return;
		}

		// Aggiunta al carrello via AJAX: mostra subito il riepilogo.
		$( document.body ).on( 'added_to_cart', function () {
			refreshFab();
			open();
		} );

		// I frammenti hanno riscritto il contatore: ricontrolla lo stato.
		$( document.body ).on( 'wc_fragments_refreshed wc_fragments_loaded', refreshFab );
	}

	if ( 'loading' === document.readyState ) {
		document.addEventListener( 'DOMContentLoaded', init );
	} else {
		init();
	}

	window.WCLGCart = { open: open, close: close, refresh: refreshFab };
} )( window.jQuery );
