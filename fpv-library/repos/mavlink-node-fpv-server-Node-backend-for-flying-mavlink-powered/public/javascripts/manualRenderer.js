class ManualRenderer {
  constructor(renderFunction) {
    this.renderFunction = renderFunction;
  }

  /**
   * Should be called by main render thread.
   * @param  {context} context Context of a cavnas to draw to.
   * @return nothing
   */
  render(context) {
    this.renderFunction(context);
  }
}