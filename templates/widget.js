/**
 * White Rabbit AI Chatbot — WordPress Widget
 * 
 * Usage: Add to WordPress footer:
 *   <script src="https://YOUR-BOT-URL.com/widget.js"></script>
 * 
 * That's it. No other configuration needed.
 * The widget loads branding from the bot's /config.js endpoint.
 */
(function() {
  // Auto-detect bot URL — find widget.js script tag reliably
  // (can't use scripts[scripts.length - 1] because defer/async changes load order)
  const allScripts = document.getElementsByTagName('script');
  let thisScript = null;
  for (let i = allScripts.length - 1; i >= 0; i--) {
    if (allScripts[i].src && /\/widget\.js(\?|$)/.test(allScripts[i].src)) {
      thisScript = allScripts[i];
      break;
    }
  }
  if (!thisScript) {
    console.error('[askrabbit widget] Cannot find widget.js script tag — aborting');
    return;
  }
  const BOT_URL = thisScript.src.replace(/\/widget\.js.*$/, '');

  // Inject styles
  const style = document.createElement('style');
  style.textContent = `
    #wr-bot-toggle {
      position: fixed; bottom: 24px; right: 24px;
      width: 64px; height: 64px; border-radius: 50%;
      border: none; cursor: pointer; z-index: 99998;
      display: flex; align-items: center; justify-content: center;
      overflow: visible;
      font-size: 32px; transition: transform 0.2s, box-shadow 0.2s;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      background: #3d0c0e;
    }
    #wr-bot-toggle:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(0,0,0,0.4); }
    #wr-bot-toggle .bot-avatar {
      position: absolute; height: 150%; width: auto;
      top: -30%; left: 50%; transform: translateX(-50%);
      pointer-events: none;
    }
    #wr-bot-toggle .bot-close {
      display: none; font-size: 24px; line-height: 1;
    }
    #wr-bot-toggle.open .bot-avatar { display: none; }
    #wr-bot-toggle.open .bot-close { display: block; }
    #wr-bot-frame {
      position: fixed; bottom: 100px; right: 24px;
      width: 380px; height: 600px;
      max-height: calc(100vh - 120px); max-width: calc(100vw - 48px);
      border-radius: 20px; overflow: hidden;
      box-shadow: 0 12px 48px rgba(0,0,0,0.35);
      z-index: 99999; display: none;
      border: 1px solid rgba(61,12,14,0.12);
    }
    #wr-bot-frame.open { display: block; }
    #wr-bot-frame iframe { width: 100%; height: 100%; border: none; }
    @media (max-width: 480px) {
      #wr-bot-frame { bottom: 0; right: 0; width: 100vw; height: 100vh; max-height: 100vh; max-width: 100vw; border-radius: 0; }
      #wr-bot-toggle { bottom: 16px; right: 16px; }
    }
  `;
  document.head.appendChild(style);

  // Load config to get emoji + branding
  const cfgScript = document.createElement('script');
  cfgScript.src = BOT_URL + '/config.js';
  cfgScript.onload = function() {
    const C = window.__BOTCFG__;
    const emoji = C ? C.bot.bot_emoji : '💬';
    const accent = C ? C.branding.accent : '#fdc300';
    const accentDark = C ? C.branding.primary_dark : '#333';
    const primary = C ? C.branding.primary : '#3d0c0e';
    const logoUrl = C && C.bot.logo_path ? BOT_URL + C.bot.logo_path : '';
    const avatarBg = (C && C.bot.avatar_bg) || primary;

    // Closed button: avatar_bg circle, <img> inside overflows slightly
    // (head + staff extend beyond the circle — Prokop-style).
    // Open button: primary color with ✕ (avatar hidden via CSS).
    if (logoUrl) {
      const avatar = document.createElement('img');
      avatar.className = 'bot-avatar';
      avatar.src = logoUrl;
      avatar.alt = '';
      toggle.appendChild(avatar);
    } else {
      toggle.textContent = emoji;
    }
    const closeSpan = document.createElement('span');
    closeSpan.className = 'bot-close';
    closeSpan.textContent = '✕';
    toggle.appendChild(closeSpan);

    toggle.style.background = avatarBg;
    document.body.appendChild(toggle);

    toggle.addEventListener('click', () => {
      const open = frame.classList.toggle('open');
      toggle.classList.toggle('open', open);
      toggle.style.background = open ? primary : avatarBg;
      toggle.style.color = open ? accent : accentDark;

      if (open && !frame.querySelector('iframe')) {
        const iframe = document.createElement('iframe');
        iframe.src = BOT_URL + '/?source=widget';
        iframe.title = C ? C.bot.name : 'Chatbot';
        frame.appendChild(iframe);
      }
    });
  };
  document.head.appendChild(cfgScript);

  // Create elements — toggle is NOT appended to body yet, that happens
  // inside cfgScript.onload after the logo/styling is set, to avoid
  // a flash of a generic icon before the branded avatar loads.
  const toggle = document.createElement('button');
  toggle.id = 'wr-bot-toggle';
  toggle.setAttribute('aria-label', 'Zeptej se Diviciaca');

  const frame = document.createElement('div');
  frame.id = 'wr-bot-frame';

  document.body.appendChild(frame);
})();
