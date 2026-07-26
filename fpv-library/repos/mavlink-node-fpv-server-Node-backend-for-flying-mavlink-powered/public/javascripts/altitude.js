class AltitudeHandler {
  constructor(rpc) {
    this.rpc = rpc;
    this.c = document.getElementById('altitude');
    this.context = this.c.getContext('2d');

    const width = 200;
    const height = 600;
    const fontSize = 16;

    const graphicsManager = new GraphicsManager(this.c);
    const majorLineRenderer = new LineRenderer({
      from: 0,
      to: height,
      lineDistance: 40,
      lineOffset: -20,
      pixelsPerUnit: 40,
      onDrawLine: this._drawLine(40)
    });

    const minorLineRenderer = new LineRenderer({
      from: 0,
      to: height,
      lineDistance: 40,
      lineOffset: 0,
      pixelsPerUnit: 40,
      onDrawLine: this._drawLine(20)
    });

    const borderedTextRenderer = new BorderedTextRenderer({
      x: 15,
      y: (height + fontSize) / 2 - 4,
      padding: 10,
      fontHeight: fontSize,
      borderThickness: 1.5,
      font: window.theme.numberFont
    });

    const verticalSpeedGauge = new BarGaugeRenderer({
      from: { x: 100, y: 0 },
      to: { x: 105, y: height },
      center: 0,
      amplitude: 10
    });

    const speedGaugeHelper = new ManualRenderer(function (context) {
      context.strokeStyle = context.fillStyle = context.shadowColor = window.theme.mainColor;
      context.fillRect(100, 0, 1, height/2);
      context.fillRect(105, 0, 1, height/2);

      context.strokeStyle = context.fillStyle = context.shadowColor = window.theme.redColor;
      context.fillRect(100, height/2, 1, height/2);
      context.fillRect(105, height/2, 1, height/2);
    });

    graphicsManager.addDrawables([majorLineRenderer, minorLineRenderer, borderedTextRenderer,  verticalSpeedGauge, speedGaugeHelper]);
    graphicsManager.startDrawing();

    rpc.on('fields.alt', (altitude) => {
      majorLineRenderer.setValue(altitude);
      minorLineRenderer.setValue(altitude);
      borderedTextRenderer.setValue(altitude);
    });

    rpc.on('fields.climb', (climb) => {
      verticalSpeedGauge.setValue(climb);
    });
  }

  _drawLine(lineLength) {
    return (context, y, lineValue) => {
      let localLineLength = lineLength;
      if (lineValue < 0.1 && lineValue > -0.1) {
        localLineLength = 1.5 * localLineLength;
      }

      if (lineValue < -0.1) {
        context.strokeStyle = context.shadowColor = window.theme.redColor;
      } else {
        context.strokeStyle = context.shadowColor = window.theme.mainColor;
      }
      
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(112, y);
      context.lineTo(112 + localLineLength, y); // bottom left
      context.stroke();
    }
  }
}