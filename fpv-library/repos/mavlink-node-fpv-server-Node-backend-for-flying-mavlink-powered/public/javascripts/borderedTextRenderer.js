class BorderedTextRenderer {
  constructor(options) {
    this.x = options.x;
    this.y = options.y;
    this.padding = options.padding;
    this.fontHeight = options.fontHeight;
    this.borderThickness = options.borderThickness;
    this.font = options.font;
    this.value = 0;
  }

  /**
   * Should be called by main render thread.
   * @param  {context} context Context of a cavnas to draw to.
   * @return nothing
   */
  render(context) {
    let text = '';
    if (this.value < 10 && this.value > -10) {
      text = (Math.round(this.value * 100) / 100).toString();
    } else if (this.value < 100 && this.value > -100) {
      text = (Math.round(this.value * 10) / 10).toString();
    } else {
      text = Math.round(this.value).toString();
    }
    const textWidth = context.measureText('-0.00').width;
    const textHeight = this.fontHeight - 4;

    context.font = `${this.fontHeight}px '${this.font}'`;
    context.fillStyle = context.shadowColor = window.theme.mainColor;
    context.fillText(text, this.x, this.y);

    context.beginPath();
    context.lineWidth = this.lineThickness;
    context.strokeStyle = context.shadowColor = window.theme.mainColor;
    context.moveTo(this.x - this.padding, this.y - textHeight - this.padding); // top left
    context.lineTo(this.x - this.padding, this.y + this.padding); // bottom left
    context.lineTo(this.x + textWidth + this.padding, this.y + this.padding); // bottom right
    context.lineTo(this.x + textWidth + this.padding + 10, this.y - textHeight/2); // center right
    context.lineTo(this.x + textWidth + this.padding, this.y - textHeight - this.padding); // top right
    context.lineTo(this.x - this.padding, this.y - textHeight - this.padding); // top left
    context.stroke();
  }

  setValue(value) {
    this.value = value;
  }
}