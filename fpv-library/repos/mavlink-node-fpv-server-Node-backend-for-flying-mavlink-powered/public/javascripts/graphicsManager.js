class GraphicsManager {
  constructor(canvas) {
    this.canvas = canvas;
    this.context = canvas.getContext("2d");
    this.memoryCanvas = document.createElement("canvas");
    this.memoryContext = canvas.getContext("2d");
    this.drawables = [];
    this.rotation = 0; // in radians
    this.drawRotation = 0;
    this.isDrawing = false;
    this.wrapValue = Math.PI * 2;
  }

  startDrawing() {
    this.isDrawing = true;
    window.requestAnimationFrame(this._draw.bind(this));
  }

  stopDrawing() {
    this.isDrawing = false;
  }

  addDrawable(drawable) {
    this.drawables.push(drawable);
  }

  addDrawables(drawables) {
    for (var i = 0; i < drawables.length; i++) {
      this.drawables.push(drawables[i]);
    };
  }

  setRotation(rotation) {
    this.rotation = rotation;
  }

  _draw() {
    if (!this.isDrawing) return;
    const angleDiff = ((((this.rotation - this.drawRotation) % this.wrapValue) + this.wrapValue*1.5) % this.wrapValue) - this.wrapValue/2;
    this.drawRotation += angleDiff * 0.05;
    this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.context.translate(this.canvas.width/2, this.canvas.height/2);
    this.context.rotate(this.drawRotation);
    this.context.translate(-this.canvas.width/2, -this.canvas.height/2);
    for (let i = 0; i < this.drawables.length; ++i) {
      this.drawables[i].render(this.context);
    }
    this.context.setTransform(1, 0, 0, 1, 0, 0);
    window.requestAnimationFrame(this._draw.bind(this));
  }
}