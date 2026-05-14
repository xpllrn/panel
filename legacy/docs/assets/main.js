(function () {
  var menuBtn = document.getElementById("menu-btn");
  var navList = document.getElementById("nav-list");
  var langButtons = document.querySelectorAll("[data-lang-btn]");
  var themeBtn = document.getElementById("theme-btn");

  function applyTheme(theme) {
    var mode = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", mode);

    if (themeBtn) {
      var isDark = mode === "dark";
      themeBtn.setAttribute("aria-pressed", String(isDark));
      themeBtn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
    }

    try {
      localStorage.setItem("site_theme", mode);
    } catch (err) {
      // no-op
    }
  }

  function applyLanguage(lang) {
    document.documentElement.lang = lang === "hi" ? "hi" : "en";
    document.body.setAttribute("data-lang", lang);

    var textNodes = document.querySelectorAll("[data-en][data-hi]");
    textNodes.forEach(function (node) {
      node.textContent = lang === "hi" ? node.getAttribute("data-hi") : node.getAttribute("data-en");
    });

    var placeholders = document.querySelectorAll("[data-en-placeholder][data-hi-placeholder]");
    placeholders.forEach(function (node) {
      node.placeholder = lang === "hi" ? node.getAttribute("data-hi-placeholder") : node.getAttribute("data-en-placeholder");
    });

    langButtons.forEach(function (btn) {
      var isActive = btn.getAttribute("data-lang-btn") === lang;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-pressed", String(isActive));
    });

    var langSwitch = document.querySelector(".lang-switch");
    if (langSwitch) {
      var enLabel = langSwitch.getAttribute("data-en-label");
      var hiLabel = langSwitch.getAttribute("data-hi-label");
      if (enLabel && hiLabel) {
        langSwitch.setAttribute("aria-label", lang === "hi" ? hiLabel : enLabel);
      }
    }

    try {
      localStorage.setItem("site_lang", lang);
    } catch (err) {
      // no-op
    }
  }

  if (menuBtn && navList) {
    menuBtn.addEventListener("click", function () {
      var open = navList.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", String(open));
    });
  }

  if (langButtons.length) {
    langButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyLanguage(btn.getAttribute("data-lang-btn"));
      });
    });
  }

  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      applyTheme(current === "dark" ? "light" : "dark");
    });
  }

  var revealItems = document.querySelectorAll(".card, .panel, .stat-card, .quote, .notice-card");
  if ("IntersectionObserver" in window && revealItems.length) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("reveal-in");
        }
      });
    }, { threshold: 0.1 });
    revealItems.forEach(function (item) {
      item.classList.add("reveal-item");
      observer.observe(item);
    });
  }

  var savedLang = "en";
  try {
    savedLang = localStorage.getItem("site_lang") || "en";
  } catch (err) {
    savedLang = "en";
  }
  var savedTheme = "light";
  try {
    savedTheme = localStorage.getItem("site_theme") || "";
  } catch (err) {
    savedTheme = "";
  }
  if (!savedTheme && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    savedTheme = "dark";
  }
  applyTheme(savedTheme || "light");
  applyLanguage(savedLang);
})();
