class BarGaugeRenderer {
  constructor(options) {
    this.from = options.from;
    this.to = options.to;
    this.centerY = this.from.y + (this.to.y - this.from.y) / 2;
    this.value = 0;
    this.drawValue = 0;
    this.amplitude = options.amplitude;
    this.center = options.center;
  }

  /**
   * Should be called by main render thread.
   * @param  {context} context Context of a cavnas to draw to.
   * @return nothing
   */
  render(context) {
    if (Math.abs(this.value - this.min) < 0.01) return;
    if (this.value < this.center) {
      context.strokeStyle = context.fillStyle = context.shadowColor = window.theme.redColor;
    } else {
      context.strokeStyle = context.fillStyle = context.shadowColor = window.theme.mainColor;
    }
    this.drawValue += (this.value - this.drawValue) * 0.05;
    let height = (this.to.y - this.from.y) * ((this.drawValue - this.center) / (this.amplitude - this.center)) / 2;
    context.fillRect(this.from.x, this.centerY, this.to.x - this.from.x, -height);
  }

  setValue(value) {
    if (value < this.center - this.amplitude) {
      this.value = this.center - this.amplitude;
    } else if (value > this.center + this.amplitude) {
      this.value = this.center + this.amplitude;
    } else {
      this.value = value;
    }
  }
}