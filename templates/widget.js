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
  // Auto-detect bot URL from script src
  const scripts = document.getElementsByTagName('script');
  const thisScript = scripts[scripts.length - 1];
  const BOT_URL = thisScript.src.replace(/\/widget\.js.*$/, '');

  // Inject styles
  const style = document.createElement('style');
  style.textContent = `
    #wr-bot-toggle {
      position: fixed; bottom: 24px; right: 24px;
      width: 64px; height: 64px; border-radius: 50%;
      border: none; cursor: pointer; z-index: 99998;
      display: flex; align-items: center; justify-content: center;
      font-size: 32px; transition: transform 0.2s, box-shadow 0.2s;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      background: #3d0c0e;
    }
    #wr-bot-toggle:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(0,0,0,0.4); }
    #wr-bot-toggle.open { background: #2a0809; font-size: 24px; }
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

    // Update toggle style with actual brand colors
    toggle.style.background = `linear-gradient(135deg, ${accent} 0%, ${accent}dd 100%)`;
    toggle.textContent = emoji;

    toggle.addEventListener('click', () => {
      const open = frame.classList.toggle('open');
      toggle.classList.toggle('open', open);
      toggle.textContent = open ? '✕' : emoji;
      toggle.style.background = open ? accentDark : `linear-gradient(135deg, ${accent} 0%, ${accent}dd 100%)`;
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

  // Create elements
  const toggle = document.createElement('button');
  toggle.id = 'wr-bot-toggle';
  toggle.setAttribute('aria-label', 'Open chatbot');
  toggle.textContent = '💬';

  const frame = document.createElement('div');
  frame.id = 'wr-bot-frame';

  document.body.appendChild(frame);
  document.body.appendChild(toggle);
})();
