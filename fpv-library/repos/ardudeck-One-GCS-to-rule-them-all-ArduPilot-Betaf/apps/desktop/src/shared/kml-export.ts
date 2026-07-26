export type ExportArea = {
  name?: string;
  polygon: { lat: number; lng: number }[];
  holes?: { lat: number; lng: number }[][];
};

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function ringCoordinates(points: { lat: number; lng: number }[]): string {
  const tuples = points.map((p) => `${p.lng},${p.lat},0`);
  // Close the ring by repeating the first coordinate
  const first = tuples[0];
  if (first !== undefined) {
    tuples.push(first);
  }
  return tuples.join(' ');
}

export function areasToKml(areas: ExportArea[]): string {
  const placemarks = areas
    .map((area, index) => {
      if (area.polygon.length < 3) return null;

      const name = escapeXml(area.name ?? `Area ${index + 1}`);
      const outerCoords = ringCoordinates(area.polygon);

      const innerBoundaries = (area.holes ?? [])
        .map((hole) => {
          const coords = ringCoordinates(hole);
          return (
            `      <innerBoundaryIs><LinearRing><coordinates>${coords}</coordinates></LinearRing></innerBoundaryIs>`
          );
        })
        .join('\n');

      return [
        '  <Placemark>',
        `    <name>${name}</name>`,
        '    <Polygon>',
        `      <outerBoundaryIs><LinearRing><coordinates>${outerCoords}</coordinates></LinearRing></outerBoundaryIs>`,
        innerBoundaries,
        '    </Polygon>',
        '  </Placemark>',
      ]
        .filter((line) => line.trim() !== '')
        .join('\n');
    })
    .filter((pm): pm is string => pm !== null);

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<kml xmlns="http://www.opengis.net/kml/2.2">',
    '<Document>',
    ...placemarks,
    '</Document>',
    '</kml>',
  ].join('\n');
}
