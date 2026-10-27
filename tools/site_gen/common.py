# -*- coding: utf-8 -*-
import os
import re
SITE = "https://normaot.ru"
# Output folder. Default: the working copy of the site. To preview/diff first:  set SITE_OUT=C:\tmp\site_preview
SITE_OUT = os.environ.get("SITE_OUT", r"D:\Project\public_html")
# True: preliminary Linux packages are on the site (download buttons, counter keys reestr-deb/-rpm/-linux).
# Compatibility with Astra Linux / Alt is still NOT confirmed by the OS vendors, so every page must say
# "preliminary build"; never declare compatibility before the documents exist (docs/LINUX_COMPAT_DOCS.md).
LINUX_PUBLISHED = True
VER = "3.9.1"; BUILD = "27.10.2026"; SIZE = "70 662 879 байт (≈ 67 МБ)"
SHA = "11c237277460def0b165ce4af683be3768507f4e64434386ab194c7dddd54636"
LINUX_FILES = [  # (download key, file, size in MB, SHA-256, human name)
    ("reestr-deb", "normaot-reestr_3.9.1_amd64.deb", "57", "5305f234547bc4c8765f42972b89bcad751d976e5cd0bf4adccc2c40e17f064f", "Astra Linux (.deb)"),
    ("reestr-rpm", "normaot-reestr-3.9.1-alt1.x86_64.rpm", "79", "6f52aba542c71bf1c5e758c08d85e20d71c22f01ea1c589fb7d9a94dad9c7ac7", "Альт (.rpm)"),
    ("reestr-linux", "normaot-reestr-3.9.1-linux-x86_64.tar.gz", "79", "fec355b4bd61f808d1d28f46451303a05a1c33426c2002d9fa8a133a0b03fcbc", "Linux (.tar.gz)"),
]
HIDE = True  # True: заглушки [УТОЧНИТЬ] не выводятся (пока владелец не заполнил); False: показать
def TODO(s, pre=""):
    return "" if HIDE else pre + '<span class="todo">[УТОЧНИТЬ: %s]</span>' % s

HEAD = '''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<script>(function(){var t;try{t=localStorage.getItem("theme")}catch(e){}if(t!=="light"&&t!=="dark"){t=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.setAttribute("data-theme",t)})()</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>%(title)s — Норма ОТ: Реестр обучения</title>
<meta name="description" content="%(desc)s" />
<meta name="robots" content="index, follow" />
<link rel="canonical" href="%(url)s" />
<meta property="og:title" content="%(title)s — Норма ОТ: Реестр обучения" />
<meta property="og:description" content="%(desc)s" />
<meta property="og:type" content="website" />
<meta property="og:url" content="%(url)s" />
<meta property="og:image" content="https://normaot.ru/assets/og-reestr.png" />
<meta property="og:locale" content="ru_RU" />
<meta name="theme-color" content="#150f23" />
<link rel="icon" href="/favicon.ico?v=390" sizes="any" />
<link rel="icon" type="image/png" sizes="180x180" href="/assets/icon-180.png?v=390" />
<link rel="preload" href="/assets/fonts/rubik-cyrillic.woff2" as="font" type="font/woff2" crossorigin />
<link rel="stylesheet" href="/assets/fonts.css?v=20261024" />
<link rel="stylesheet" href="/assets/docs.css?v=20261022" />
<link rel="stylesheet" href="/assets/theme.css?v=20261020" />
</head>
<body>
<a class="skip" href="#main">К содержанию</a>
<header class="nav" id="nav">
  <div class="wrap nav__in">
    <a class="brand" href="/index.html" aria-label="Норма ОТ">
      <img width="128" height="128" src="/assets/icon-128.webp?v=390" alt="Логотип Норма ОТ" onerror="this.style.display='none'" />
      <span class="brand__txt"><b>Норма&nbsp;ОТ</b><i>Программы для охраны труда</i></span>
    </a>
    <nav class="nav__links" aria-label="Навигация">
      <a href="/index.html">Все программы</a>
      <a href="/reestr.html">Реестр обучения</a>
      <a href="/docs/index.html">Документация</a>
      <a href="/blog.html">Блог</a>
      <a href="/about.html">О проекте</a>
      <a href="/contacts.html">Контакты</a>
    </nav>
    <div class="nav__tools"><button class="theme-toggle" type="button" aria-label="Переключить тему"><svg class="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg><svg class="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></button><button class="nav__burger" aria-label="Меню" onclick="document.getElementById('nav').classList.toggle('open')">☰</button></div>
  </div>
</header>
'''

FOOT = '''
<svg class="squiggle" viewBox="0 0 1200 20" preserveAspectRatio="none" aria-hidden="true"><path d="M0 10 Q 30 0 60 10 T 120 10 T 180 10 T 240 10 T 300 10 T 360 10 T 420 10 T 480 10 T 540 10 T 600 10 T 660 10 T 720 10 T 780 10 T 840 10 T 900 10 T 960 10 T 1020 10 T 1080 10 T 1140 10 T 1200 10" fill="none" stroke="currentColor" stroke-width="3"/></svg>

<footer class="footer">
  <div class="wrap">
    <div class="footer__grid">
      <div class="footer__col">
        <h4>Норма ОТ: Реестр обучения</h4>
        <p>Windows-программа без рекламы для специалистов по охране труда. Open source проект.</p>
      </div>
      <div class="footer__col">
        <h4>Программы</h4>
        <a href="/reestr.html">Реестр обучения</a>
        <a href="/protokoly-eb.html">Протокол ЭБ</a>
        <a href="/guide.html">Руководство</a>
        <a href="/changelog.html">История версий</a>
      </div>
      <div class="footer__col">
        <h4>Информация</h4>
        <a href="/docs/index.html">Документация</a>
        <a href="/rightsholder.html">Правообладатель</a>
        <a href="/components.html">Сторонние компоненты</a>
        <a href="/about.html">О проекте</a>
        <a href="/contacts.html">Контакты</a>
        <a href="/privacy.html">Политика конфиденциальности</a>
        <a href="/terms.html">Пользовательское соглашение</a>
        <a href="/license.html">Лицензия поддержки</a>
      </div>
      <div class="footer__col">
        <h4>Контакты</h4>
        <a href="mailto:denis.krv@yandex.ru">denis.krv@yandex.ru</a>
        <a href="https://gitflic.ru/project/denis-krv/norma_ot_reestr" target="_blank" rel="noopener">GitFlic: Реестр обучения</a>
        <a href="https://github.com/Kerlad/norma_ot_reestr" target="_blank" rel="noopener">GitHub: Реестр обучения</a>
      </div>
    </div>
    <div class="footer__bottom">
      <div>© 2024–2026 Норма ОТ. Код доступен под лицензией MIT.</div>
      <div><a href="https://github.com/Kerlad">Кривоносов Д.А.</a> · <a href="/index.html">normaot.ru</a></div>
    </div>
  </div>
</footer>

<script>
(function(){
  var nav=document.getElementById('nav');
  document.querySelectorAll('.nav__links a').forEach(function(a){
    a.addEventListener('click',function(){ nav.classList.remove('open'); });
  });
})();
</script>
<!-- Yandex.Metrika counter -->
<script type="text/javascript">
    (function(m,e,t,r,i,k,a){
        m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
        m[i].l=1*new Date();
        for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
    })(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=110179627', 'ym');
    ym(110179627, 'init', {ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", referrer: document.referrer, url: location.href, accurateTrackBounce:true, trackLinks:true});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/110179627" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<script src="/assets/theme.js?v=20261020" defer></script>
</body>
</html>
'''

def page(path, title, desc, eyebrow, h1, lead, body, doc_tools=False):
    url = SITE + "/" + path
    tools = ''
    if doc_tools:
        tools = ('<div class="doc-tools"><button type="button" onclick="window.print()">Печать / сохранить как PDF</button>'
                 '<a href="/docs/index.html">Все документы</a></div>\n')
    if HIDE:
        body = re.sub(r"<tr><td>(?:(?!</tr>).)*?</td><td>\s*</td></tr>\n?", "", body, flags=re.S)
        body = re.sub(r"<table>\s*</table>\n?|<p>\s*</p>\n?", "", body)
    out = HEAD % dict(title=title, desc=desc, url=url)
    if path.startswith("docs/"):
        out = out.replace('<a href="/docs/index.html">', '<a href="/docs/index.html" class="is-active">', 1)
    out += '''
<main id="main">
  <section class="phero">
    <div class="wrap">
      <span class="eyebrow">%s</span>
      <h1>%s</h1>
      <p>%s</p>
    </div>
  </section>

  <section class="sec-dark">
    <div class="wrap legal">
%s%s
    </div>
  </section>
</main>
''' % (eyebrow, h1, lead, tools, body)
    out += FOOT
    dest = os.path.join(SITE_OUT, path.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print("wrote", path, len(out))
