import L from 'leaflet';

/**
 * Rocket icon used to render NAV_TAKEOFF at the home position when the
 * underlying mission item carries placeholder (0,0) coordinates.
 */
export const TAKEOFF_AT_HOME_ICON = L.divIcon({
  className: 'takeoff-marker',
  html: `
    <div style="
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
      transform: translate(14px, -14px);
    ">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="#fbbf24" stroke="#7c2d12" stroke-width="1.5" stroke-linejoin="round">
        <path d="M12 2c2.5 3 4 6 4 9v4l2 3v2l-3-1-3 1-3-1-3 1v-2l2-3v-4c0-3 1.5-6 4-9z"/>
        <circle cx="12" cy="10" r="1.5" fill="#7c2d12"/>
      </svg>
    </div>
  `,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});
