import { WMSTileLayer } from 'react-leaflet';

const DIPUL_WMS_URL = 'https://uas-betrieb.de/geoservices/dipul/wms';

const DEFAULT_LAYERS = [
  'kontrollzonen',
  'flugbeschraenkungsgebiete',
  'flughaefen',
  'flugplaetze',
  'modellflugplaetze',
  'naturschutzgebiete',
  'nationalparks',
  'krankenhaeuser',
  'polizei',
  'justizvollzugsanstalten',
  'militaerische_anlagen',
  'bundesautobahnen',
  'bundesstrassen',
  'industrieanlagen',
  'kraftwerke',
  'umspannwerke',
].join(',');

export function DipulOverlay() {
  return (
    <WMSTileLayer
      url={DIPUL_WMS_URL}
      layers={DEFAULT_LAYERS}
      format="image/png"
      transparent={true}
      version="1.3.0"
      opacity={0.7}
      zIndex={5}
      attribution='DIPUL &copy; DFS, BKG'
    />
  );
}
