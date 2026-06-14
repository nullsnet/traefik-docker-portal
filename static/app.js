/**
 * Theme Manager - Handles dark/light theme switching and persistence
 */
const ThemeManager = {
  STORAGE_KEY: 'bsTheme',

  init() {
    const savedTheme = this.getSavedTheme();
    if (savedTheme) {
      this.applyTheme(savedTheme);
    } else {
      this.applyTheme(this.getSystemPreference());
    }
    this.bindEvents();
  },

  getSavedTheme() {
    return localStorage.getItem(this.STORAGE_KEY);
  },

  getSystemPreference() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  },

  applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
  },

  toggleTheme() {
    const current = document.documentElement.getAttribute('data-bs-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    this.applyTheme(next);
    localStorage.setItem(this.STORAGE_KEY, next);
  },

  bindEvents() {
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => this.toggleTheme());
    }
  }
};

/**
 * Service Worker Manager - Handles service worker registration
 */
const ServiceWorkerManager = {
  SW_PATH: '/static/sw.js',

  init() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => this.register());
    }
  },

  register() {
    navigator.serviceWorker.register(this.SW_PATH)
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.log('SW registration failed:', err));
  }
};

/**
 * Application initialization
 */
const App = {
  init() {
    ThemeManager.init();
    ServiceWorkerManager.init();
  }
};

// Start the application
document.addEventListener('DOMContentLoaded', () => App.init());
