import { calculateActualRate, calculateThrottle } from './rate-calculator.js';

/**
 * Renders comparison graphs for rate profiles
 */
export class GraphRenderer {
  constructor(rateCanvas, throttleCanvas) {
    this.rateCanvas = rateCanvas;
    this.throttleCanvas = throttleCanvas;
    this.rateCtx = rateCanvas.getContext('2d');
    this.throttleCtx = throttleCanvas.getContext('2d');

    // Visual configuration
    this.colors = {
      roll: '#ff3366',    // Red
      pitch: '#33ff66',   // Green
      yaw: '#ffaa00'      // Orange
    };

    this.padding = 60;
    this.gridColor = '#333';
    this.axisColor = '#666';
    this.labelColor = '#999';

    // Visibility settings
    this.visibility = {
      profileA: true,
      profileB: true,
      roll: true,
      pitch: true,
      yaw: true
    };
  }

  /**
   * Set visibility for profiles and attitudes
   * @param {Object} visibility - Visibility settings
   */
  setVisibility(visibility) {
    this.visibility = { ...this.visibility, ...visibility };
  }

  /**
   * Clear a canvas
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} width
   * @param {number} height
   */
  clearCanvas(ctx, width, height) {
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);
  }

  /**
   * Draw grid on canvas
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} width
   * @param {number} height
   */
  drawGrid(ctx, width, height) {
    ctx.strokeStyle = this.gridColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);

    // Vertical grid lines
    for (let i = 0; i <= 10; i++) {
      const x = this.padding + (width - 2 * this.padding) * (i / 10);
      ctx.beginPath();
      ctx.moveTo(x, this.padding);
      ctx.lineTo(x, height - this.padding);
      ctx.stroke();
    }

    // Horizontal grid lines
    for (let i = 0; i <= 10; i++) {
      const y = this.padding + (height - 2 * this.padding) * (i / 10);
      ctx.beginPath();
      ctx.moveTo(this.padding, y);
      ctx.lineTo(width - this.padding, y);
      ctx.stroke();
    }

    ctx.setLineDash([]);
  }

  /**
   * Draw axes for rate graph
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} width
   * @param {number} height
   * @param {number} yMax
   */
  drawRateAxes(ctx, width, height, yMax) {
    ctx.strokeStyle = this.axisColor;
    ctx.lineWidth = 2;

    // Y-axis
    ctx.beginPath();
    ctx.moveTo(this.padding, this.padding);
    ctx.lineTo(this.padding, height - this.padding);
    ctx.stroke();

    // X-axis (centered)
    ctx.beginPath();
    ctx.moveTo(this.padding, height / 2);
    ctx.lineTo(width - this.padding, height / 2);
    ctx.stroke();

    // Labels
    ctx.fillStyle = this.labelColor;
    ctx.font = '12px monospace';
    ctx.textAlign = 'right';

    // Y-axis labels
    for (let i = 0; i <= 4; i++) {
      const value = yMax - (i * yMax / 2);
      const y = this.padding + (height - 2 * this.padding) * (i / 4);
      ctx.fillText(Math.round(value) + '°/s', this.padding - 10, y + 4);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    ctx.fillText('-1.0', this.padding, height - this.padding + 20);
    ctx.fillText('0.0', width / 2, height - this.padding + 20);
    ctx.fillText('1.0', width - this.padding, height - this.padding + 20);
    ctx.fillText('RC Command', width / 2, height - 10);
  }

  /**
   * Draw axes for throttle graph
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} width
   * @param {number} height
   */
  drawThrottleAxes(ctx, width, height) {
    ctx.strokeStyle = this.axisColor;
    ctx.lineWidth = 2;

    // Y-axis and X-axis
    ctx.beginPath();
    ctx.moveTo(this.padding, this.padding);
    ctx.lineTo(this.padding, height - this.padding);
    ctx.lineTo(width - this.padding, height - this.padding);
    ctx.stroke();

    // Labels
    ctx.fillStyle = this.labelColor;
    ctx.font = '12px monospace';
    ctx.textAlign = 'right';

    // Y-axis labels
    for (let i = 0; i <= 10; i++) {
      const value = 1.0 - (i / 10);
      const y = this.padding + (height - 2 * this.padding) * (i / 10);
      ctx.fillText(value.toFixed(1), this.padding - 10, y + 4);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    for (let i = 0; i <= 10; i++) {
      const value = i / 10;
      const x = this.padding + (width - 2 * this.padding) * (i / 10);
      ctx.fillText(value.toFixed(1), x, height - this.padding + 20);
    }

    ctx.fillText('Throttle Input', width / 2, height - 10);

    // Y-axis label (rotated)
    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Throttle Output', 0, 0);
    ctx.restore();
  }

  /**
   * Draw a single rate curve
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} width
   * @param {number} height
   * @param {Object} rates - Rate settings for specific axis
   * @param {string} color - Curve color
   * @param {number} yMax - Maximum Y value for scaling
   * @param {boolean} dashed - Whether to use dashed line
   */
  drawRateCurve(ctx, width, height, rates, color, yMax, dashed = false) {
    const steps = 200;

    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.setLineDash(dashed ? [10, 5] : []);
    ctx.beginPath();

    for (let i = 0; i <= steps; i++) {
      const rcCommand = -1 + (2 * i / steps);
      const rateValue = calculateActualRate(
        rcCommand,
        rates.center,
        rates.maxRate,
        rates.expo
      );

      const x = this.padding + (width - 2 * this.padding) * ((rcCommand + 1) / 2);
      const y = (height / 2) - ((rateValue / yMax) * (height - 2 * this.padding) / 2);

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
    ctx.setLineDash([]);
  }

  /**
   * Draw throttle curve
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} width
   * @param {number} height
   * @param {Object} throttle - Throttle settings
   * @param {string} color - Curve color
   * @param {boolean} dashed - Whether to use dashed line
   */
  drawThrottleCurve(ctx, width, height, throttle, color, dashed = false) {
    const steps = 200;

    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.setLineDash(dashed ? [10, 5] : []);
    ctx.beginPath();

    for (let i = 0; i <= steps; i++) {
      const input = i / steps;
      const throttleValue = calculateThrottle(
        input,
        throttle.mid,
        throttle.expo,
        throttle.limitType,
        throttle.limitPercent,
      );

      const x = this.padding + (width - 2 * this.padding) * input;
      const y = height - this.padding - (height - 2 * this.padding) * throttleValue;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
    ctx.setLineDash([]);
  }

  /**
   * Calculate maximum rate for scaling
   * @param {Object} profileA
   * @param {Object} profileB
   * @returns {number} Maximum rate value
   */
  calculateMaxRate(profileA, profileB) {
    const axes = ['roll', 'pitch', 'yaw'];
    let maxRate = 0;

    axes.forEach(axis => {
      if (this.visibility[axis]) {
        if (profileA && this.visibility.profileA) {
          const rate = Math.abs(calculateActualRate(
            1,
            profileA.rates[axis].center,
            profileA.rates[axis].maxRate,
            profileA.rates[axis].expo
          ));
          maxRate = Math.max(maxRate, rate);
        }

        if (profileB && this.visibility.profileB) {
          const rate = Math.abs(calculateActualRate(
            1,
            profileB.rates[axis].center,
            profileB.rates[axis].maxRate,
            profileB.rates[axis].expo
          ));
          maxRate = Math.max(maxRate, rate);
        }
      }
    });

    return Math.max(1000, maxRate * 1.1);
  }

  /**
   * Render rate comparison graph
   * @param {Object} profileA - First profile
   * @param {Object} profileB - Second profile
   */
  renderRates(profileA, profileB) {
    const width = this.rateCanvas.width;
    const height = this.rateCanvas.height;
    const ctx = this.rateCtx;

    // Clear canvas
    this.clearCanvas(ctx, width, height);

    // Draw grid
    this.drawGrid(ctx, width, height);

    // Calculate max rate for scaling
    const yMax = this.calculateMaxRate(profileA, profileB);

    // Draw curves for each visible axis
    const axes = ['roll', 'pitch', 'yaw'];
    axes.forEach(axis => {
      if (!this.visibility[axis]) return;

      if (profileA && this.visibility.profileA) {
        this.drawRateCurve(
          ctx,
          width,
          height,
          profileA.rates[axis],
          this.colors[axis],
          yMax,
          false // solid line for Profile A
        );
      }

      if (profileB && this.visibility.profileB) {
        this.drawRateCurve(
          ctx,
          width,
          height,
          profileB.rates[axis],
          this.colors[axis],
          yMax,
          true // dashed line for Profile B
        );
      }
    });

    // Draw axes
    this.drawRateAxes(ctx, width, height, yMax);
  }

  /**
   * Render throttle comparison graph
   * @param {Object} profileA - First profile
   * @param {Object} profileB - Second profile
   */
  renderThrottle(profileA, profileB) {
    const width = this.throttleCanvas.width;
    const height = this.throttleCanvas.height;
    const ctx = this.throttleCtx;

    // Clear canvas
    this.clearCanvas(ctx, width, height);

    // Draw grid
    this.drawGrid(ctx, width, height);

    // Draw throttle curves
    if (profileA && this.visibility.profileA) {
      this.drawThrottleCurve(
        ctx,
        width,
        height,
        profileA.throttle,
        '#00aaff', // Blue for throttle
        false // solid line for Profile A
      );
    }

    if (profileB && this.visibility.profileB) {
      this.drawThrottleCurve(
        ctx,
        width,
        height,
        profileB.throttle,
        '#00aaff', // Blue for throttle
        true // dashed line for Profile B
      );
    }

    // Draw axes
    this.drawThrottleAxes(ctx, width, height);
  }

  /**
   * Render both graphs
   * @param {Object} profileA - First profile
   * @param {Object} profileB - Second profile
   */
  render(profileA, profileB) {
    this.renderRates(profileA, profileB);
    this.renderThrottle(profileA, profileB);
  }
}
