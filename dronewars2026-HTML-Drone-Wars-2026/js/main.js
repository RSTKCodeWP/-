// Initialize AOS
AOS.init({
  duration: 800,
  once: true,
  offset: 80
});

// Countdown timer to June 1, 2026 00:00:00 EDT
(function () {
  var target = new Date('2026-06-01T00:00:00-04:00').getTime();
  var daysEl = document.getElementById('cd-days');
  var hoursEl = document.getElementById('cd-hours');
  var minsEl = document.getElementById('cd-mins');
  var secsEl = document.getElementById('cd-secs');

  function update() {
    var now = Date.now();
    var diff = target - now;
    if (diff <= 0) {
      daysEl.textContent = '0';
      hoursEl.textContent = '00';
      minsEl.textContent = '00';
      secsEl.textContent = '00';
      return;
    }
    var d = Math.floor(diff / 86400000);
    var h = Math.floor((diff % 86400000) / 3600000);
    var m = Math.floor((diff % 3600000) / 60000);
    var s = Math.floor((diff % 60000) / 1000);
    daysEl.textContent = d;
    hoursEl.textContent = h < 10 ? '0' + h : h;
    minsEl.textContent = m < 10 ? '0' + m : m;
    secsEl.textContent = s < 10 ? '0' + s : s;
  }

  update();
  setInterval(update, 1000);
})();

// Navbar scroll behavior
(function () {
  var navbar = document.getElementById('navbar');
  window.addEventListener('scroll', function () {
    if (window.scrollY > 50) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  });
})();

// Mobile menu toggle
(function () {
  var toggle = document.getElementById('navToggle');
  var links = document.getElementById('navLinks');

  toggle.addEventListener('click', function () {
    toggle.classList.toggle('open');
    links.classList.toggle('open');
  });

  // Close menu on link click
  var navAnchors = links.querySelectorAll('a');
  navAnchors.forEach(function (a) {
    a.addEventListener('click', function () {
      toggle.classList.remove('open');
      links.classList.remove('open');
    });
  });
})();

// Video lightbox
(function () {
  var lightbox = document.getElementById('videoLightbox');
  var iframe = document.getElementById('lightboxIframe');
  var backdrop = lightbox.querySelector('.video-lightbox-backdrop');
  var closeBtn = lightbox.querySelector('.video-lightbox-close');

  function open(src) {
    iframe.src = src + '?autoplay=1';
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function close() {
    lightbox.classList.remove('active');
    iframe.src = '';
    document.body.style.overflow = '';
  }

  document.querySelectorAll('.event-card-play').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      open(this.getAttribute('data-video'));
    });
  });

  closeBtn.addEventListener('click', close);
  backdrop.addEventListener('click', close);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && lightbox.classList.contains('active')) close();
  });
})();

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
  anchor.addEventListener('click', function (e) {
    var target = document.querySelector(this.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});
