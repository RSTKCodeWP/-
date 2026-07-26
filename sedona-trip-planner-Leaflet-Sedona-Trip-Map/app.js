// ==========================================
// SEDONA TRIP MAP — app.js
// ==========================================

document.addEventListener('DOMContentLoaded', () => {

  // Initial center: between basecamp (FR525) and Sedona town
  const SEDONA_CENTER = [34.875, -111.83];
  const INITIAL_ZOOM = 12;

  const map = L.map('map', {
    center: SEDONA_CENTER,
    zoom: INITIAL_ZOOM,
    zoomControl: true,
    scrollWheelZoom: true,
    minZoom: 10,
    maxZoom: 19,
    // Markers snap to new positions on zoom instead of animating —
    // prevents the "flying around" perception during zoom transitions.
    zoomAnimation: false,
    markerZoomAnimation: false,
    fadeAnimation: false
  });

  // GOOGLE SATELLITE tiles (hybrid: imagery + labels)
  // Using Google's tile server with the 's,h' layers for satellite + hybrid labels
  const googleSatHybrid = L.tileLayer(
    'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    {
      attribution: '&copy; Google',
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    }
  );

  const googleSatPure = L.tileLayer(
    'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    {
      attribution: '&copy; Google',
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    }
  );

  const googleTerrain = L.tileLayer(
    'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
    {
      attribution: '&copy; Google',
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    }
  );

  // Default: hybrid satellite (imagery + place labels)
  googleSatHybrid.addTo(map);

  // Layer switcher
  L.control.layers(
    {
      'Satellite (Hybrid)': googleSatHybrid,
      'Satellite (Pure)':   googleSatPure,
      'Terrain':            googleTerrain
    },
    null,
    { position: 'topright', collapsed: true }
  ).addTo(map);

  // ==========================================
  // CUSTOM PIN ICON FACTORY
  // ==========================================
  function makeIcon(pin) {
    const category = pin.category;
    const cat = CATEGORIES[category];
    const color = cat ? cat.color : '#666';
    const icon = cat ? cat.icon : '•';
    const starBadge = pin.suggested
      ? `<div class="pin-star" title="Suggested by friends & family">★</div>`
      : '';
    const heartBadge = pin.favorite
      ? `<div class="pin-heart" title="My favorite">♥</div>`
      : '';
    const skullBadge = pin.danger
      ? `<div class="pin-skull" title="Use extreme caution">☠</div>`
      : '';
    const badges = heartBadge + starBadge + skullBadge;

    // MTB: standalone bicycle silhouette, no colored teardrop background.
    // Anchor at the wheel line (cy=17.5 in viewBox 0-24 → ~73% down),
    // so the pin "sits at" the lat/lng intuitively even when zooming.
    if (category === 'mtb') {
      const size = 42;
      const anchorY = Math.round(size * (17.5 / 24));
      const bikeSvg = `
        <svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="18.5" cy="17.5" r="3.5" fill="#ffffff"/>
          <circle cx="5.5" cy="17.5" r="3.5" fill="#ffffff"/>
          <circle cx="15" cy="5" r="1" fill="${color}"/>
          <path d="M12 17.5V14l-3-3 5-4 2 3h2"/>
        </svg>`;
      return L.divIcon({
        className: 'sedona-pin sedona-pin--bike' + (pin.suggested ? ' sedona-pin--suggested' : ''),
        html: `<div class="pin-bike">${bikeSvg}${badges}</div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, anchorY],
        popupAnchor: [0, -anchorY + 2]
      });
    }

    // OHV: standalone dirt-bike silhouette in orange, no background pill.
    // Same wheel-line anchor as MTB.
    if (category === 'ohv') {
      const size = 42;
      const anchorY = Math.round(size * (17.5 / 24));
      const motoSvg = `
        <svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="${color}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="5.5" cy="17.5" r="3.8" fill="#ffffff"/>
          <circle cx="18.5" cy="17.5" r="3.8" fill="#ffffff"/>
          <path d="M5.5 17.5 L9 11 L14.5 11 L18.5 17.5 Z" fill="${color}"/>
          <path d="M14.5 11 L17.5 7 L20.5 7" />
          <path d="M9 11 L7.5 8" />
        </svg>`;
      return L.divIcon({
        className: 'sedona-pin sedona-pin--moto' + (pin.suggested ? ' sedona-pin--suggested' : ''),
        html: `<div class="pin-bike pin-moto">${motoSvg}${badges}</div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, anchorY],
        popupAnchor: [0, -anchorY + 2]
      });
    }

    const isBasecamp = category === 'basecamp';
    const klass = isBasecamp ? 'pin-marker pin-marker--basecamp' : 'pin-marker';
    const size = isBasecamp ? 44 : 36;
    // The teardrop is a square rotated -45deg. After rotation, the visual
    // tip extends below the box by size*(√2/2 - 0.5) ≈ size*0.207. Anchor
    // there so the tip actually points to the lat/lng at any zoom.
    const anchorY = Math.round(size * 1.207);

    return L.divIcon({
      className: 'sedona-pin' + (pin.suggested ? ' sedona-pin--suggested' : ''),
      html: `<div class="${klass}" style="background:${color}"><div class="pin-marker__inner">${icon}</div></div>${badges}`,
      iconSize: [size, size],
      iconAnchor: [size / 2, anchorY],
      popupAnchor: [0, -anchorY + 6]
    });
  }

  // ==========================================
  // PLACE ALL PINS
  // ==========================================
  const markers = {};
  PINS.forEach(pin => {
    const marker = L.marker([pin.lat, pin.lng], {
      icon: makeIcon(pin),
      title: pin.name
    }).addTo(map);

    const popupHtml = `
      <div class="popup-short">${CATEGORIES[pin.category].label}</div>
      <strong>${pin.name}</strong>
      ${pin.danger ? `<div class="popup-danger">☠ Use extreme caution</div>` : ''}
      ${pin.favorite ? `<div class="popup-favorite">♥ My favorite</div>` : ''}
      ${pin.suggested ? `<div class="popup-suggested">★ ${pin.suggestedBy || 'Suggested by friends & family'}</div>` : ''}
      ${pin.note ? `<div class="popup-note">📝 ${pin.note}</div>` : ''}
      ${pin.distance ? `<div style="font-size: 0.85rem; color: #6b4423; margin-bottom: 0.4rem;">${pin.distance}${pin.difficulty ? ' · ' + pin.difficulty : ''}</div>` : ''}
      ${pin.fromBasecamp ? `<div class="popup-basecamp">⛺ ${pin.fromBasecamp}</div>` : ''}
      <div style="font-size: 0.9rem; line-height: 1.4; color: #2b1810; margin-bottom: 0.5rem;">${pin.short || ''}</div>
      <a class="popup-btn" href="#" data-pin-id="${pin.id}">Open details →</a>
    `;
    marker.bindPopup(popupHtml, { maxWidth: 280 });

    marker.on('popupopen', () => {
      const btn = document.querySelector(`a.popup-btn[data-pin-id="${pin.id}"]`);
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          openModal(pin);
          map.closePopup();
        });
      }
    });

    markers[pin.id] = marker;
  });

  // Fit map to all pins
  const bounds = L.latLngBounds(PINS.map(p => [p.lat, p.lng]));
  map.fitBounds(bounds, { padding: [50, 50] });

  // ==========================================
  // MODAL
  // ==========================================
  const modal = document.getElementById('modal');
  const modalContent = document.getElementById('modal-content');
  const modalClose = modal.querySelector('.modal__close');
  const modalBackdrop = modal.querySelector('.modal__backdrop');

  function openModal(pin) {
    const cat = CATEGORIES[pin.category];

    const metaItems = [];
    if (pin.difficulty) metaItems.push(`<span>◆ ${pin.difficulty}</span>`);
    if (pin.distance)   metaItems.push(`<span>↔ ${pin.distance}</span>`);
    metaItems.push(`<span>⊕ ${pin.lat.toFixed(4)}, ${pin.lng.toFixed(4)}</span>`);

    const basecampBanner = pin.fromBasecamp
      ? `<div class="modal__basecamp">⛺ ${pin.fromBasecamp}</div>`
      : '';

    const suggestedBanner = pin.suggested
      ? `<div class="modal__suggested">★ ${pin.suggestedBy || 'Suggested by friends & family'}</div>`
      : '';

    const favoriteBanner = pin.favorite
      ? `<div class="modal__favorite">♥ My favorite</div>`
      : '';

    const noteBanner = pin.note
      ? `<div class="modal__note"><span class="modal__note-label">📝 My note</span>${pin.note}</div>`
      : '';

    const dangerBanner = pin.danger
      ? `<div class="modal__danger">☠ Use extreme caution — real consequences for mistakes</div>`
      : '';

    const tipsHtml = (pin.tips && pin.tips.length) ? `
      <div class="modal__tips">
        <div class="modal__tips-title">Field Notes</div>
        <ul>${pin.tips.map(t => `<li>· ${t}</li>`).join('')}</ul>
      </div>
    ` : '';

    const videoHtml = pin.youtube ? `
      <span class="modal__video-label">▶ POV / Trail Video${pin.youtubeTitle ? ' · ' + pin.youtubeTitle : ''}</span>
      <div class="modal__video">
        <iframe src="${pin.youtube}" title="${pin.name} video" allowfullscreen loading="lazy"></iframe>
      </div>
    ` : '';

    const linksHtml = (pin.links && pin.links.length) ? `
      <div class="modal__links">
        ${pin.links.map(l => `<a href="${l.url}" target="_blank" rel="noopener">${l.label} ↗</a>`).join('')}
        <a href="https://www.google.com/maps/dir/?api=1&destination=${pin.lat},${pin.lng}" target="_blank" rel="noopener">Directions ↗</a>
      </div>
    ` : '';

    modalContent.innerHTML = `
      <div class="modal__cat" style="background:${cat.color}">${cat.icon} ${cat.label}</div>
      <h2 class="modal__title">${pin.name}</h2>
      <div class="modal__meta">${metaItems.join('')}</div>
      ${dangerBanner}
      ${favoriteBanner}
      ${suggestedBanner}
      ${basecampBanner}
      ${noteBanner}
      <div class="modal__desc">${pin.description}</div>
      ${tipsHtml}
      ${videoHtml}
      ${linksHtml}
    `;

    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    // Stop video by clearing iframe
    const iframe = modalContent.querySelector('iframe');
    if (iframe) iframe.src = '';
  }

  modalClose.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') {
      closeModal();
    }
  });

  // ==========================================
  // selectPin — scroll to the map, fly to the pin, open its popup
  // Reused by both legend (single-pin categories) and the list views.
  // ==========================================
  function selectPin(pin) {
    document.querySelector('.map-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
    map.flyTo([pin.lat, pin.lng], Math.max(map.getZoom(), 15), { duration: 0.8 });
    setTimeout(() => markers[pin.id] && markers[pin.id].openPopup(), 550);
  }

  // ==========================================
  // LEGEND: hide entries for empty categories, wire up click → filter
  // ==========================================
  document.querySelectorAll('.legend__item').forEach(item => {
    const cat = item.dataset.cat;
    if (!PINS.some(p => p.category === cat)) {
      item.style.display = 'none';
    }
  });
  document.querySelectorAll('.legend__item').forEach(item => {
    item.style.cursor = 'pointer';
    item.addEventListener('click', () => {
      const cat = item.dataset.cat;
      const catPins = PINS.filter(p => p.category === cat);
      if (catPins.length === 0) return;
      if (catPins.length === 1) {
        selectPin(catPins[0]);
      } else {
        const b = L.latLngBounds(catPins.map(p => [p.lat, p.lng]));
        map.fitBounds(b, { padding: [80, 80] });
        document.querySelector('.map-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ==========================================
  // LIST VIEW: render <ul data-category-list="..."> from PINS.
  // Each item is clickable and keyboard-activatable — selects the pin
  // on the map (scroll + fly + popup).
  // ==========================================
  document.querySelectorAll('[data-category-list]').forEach(ul => {
    const cat = ul.dataset.categoryList;
    const catPins = PINS.filter(p => p.category === cat);
    ul.innerHTML = catPins.map(pin => {
      const meta = [pin.difficulty, pin.distance].filter(Boolean).join(' · ');
      return `
        <li class="ride-list__item" data-pin-id="${pin.id}" tabindex="0" role="button" aria-label="Show ${pin.name} on the map">
          <div class="ride-list__row">
            <strong>${pin.name}</strong>
            <div class="ride-list__badges">
              ${pin.danger ? '<span class="ride-list__skull" title="Use extreme caution">☠</span>' : ''}
              ${pin.favorite ? '<span class="ride-list__heart" title="My favorite">♥</span>' : ''}
              ${pin.suggested ? '<span class="ride-list__star" title="Suggested by friends & family">★</span>' : ''}
            </div>
          </div>
          ${meta ? `<div class="ride-list__meta">${meta}</div>` : ''}
          ${pin.short ? `<div class="ride-list__short">${pin.short}</div>` : ''}
          ${pin.note ? `<div class="ride-list__note">📝 ${pin.note}</div>` : ''}
          ${pin.fromBasecamp ? `<div class="ride-list__basecamp">⛺ ${pin.fromBasecamp}</div>` : ''}
        </li>
      `;
    }).join('');

    ul.querySelectorAll('.ride-list__item').forEach(li => {
      const handler = () => {
        const pin = PINS.find(p => p.id === li.dataset.pinId);
        if (pin) selectPin(pin);
      };
      li.addEventListener('click', handler);
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); }
      });
    });
  });

});
