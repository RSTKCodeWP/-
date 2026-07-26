class VideoHandler {
  constructor(rpc) {
    this.video = document.querySelector('img#video');
    this.isPlaying = false;
    this.timeout = 3000;
    this.timer = null;
    this.url = null;

    this.video.onerror = this._onError.bind(this);
    this.video.onload = this._onLoad.bind(this);

    rpc.on('info', (fields) => {
      const videoPath = fields.videoPath;
      this.url = `http://${videoPath.address}:${videoPath.port}/?action=stream#`;
      console.log(fields);
    });

    this._reload();
  }

  _onError() {
    this.isPlaying = false;
    this._resetTimer();
  }

  _onLoad() {
    this.isPlaying = true;
    this._resetTimer();
  }

  _resetTimer() {
    clearTimeout(this.timer);
    this.timer = setTimeout(this._reload.bind(this), this.timeout);
  }

  _reload() {
    this.isPlaying = false;
    this.video.src = this.url + Date.now();
  }
}