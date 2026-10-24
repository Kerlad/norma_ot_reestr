# -*- coding: utf-8 -*-
"""Custom 404 page (served via ErrorDocument in .htaccess). Run: python gen_404.py  (writes 404.html into SITE_OUT)."""
import os
from common import HEAD, FOOT, SITE_OUT

out = HEAD % dict(title="Страница не найдена",
                  desc="Такой страницы на сайте normaot.ru нет. Перейдите на главную, к программе «Реестр обучения» или к руководству.",
                  url="https://normaot.ru/404.html")
out = out.replace('<meta name="robots" content="index, follow" />', '<meta name="robots" content="noindex, follow" />')
out = out.replace('<link rel="canonical" href="https://normaot.ru/404.html" />\n', "")
out += '''
<main id="main">
  <section class="phero">
    <div class="wrap">
      <span class="eyebrow">Ошибка 404</span>
      <h1>Страница <span class="mark">не найдена</span></h1>
      <p>Возможно, адрес набран с ошибкой или страница переехала. Вот куда можно перейти:</p>
      <div class="doc-tools" style="justify-content:center;margin-top:24px">
        <a href="/index.html">На главную</a>
        <a href="/reestr.html">Реестр обучения</a>
        <a href="/guide.html">Руководство</a>
        <a href="/docs/index.html">Документация</a>
      </div>
    </div>
  </section>
</main>
''' + FOOT
with open(os.path.join(SITE_OUT, "404.html"), "w", encoding="utf-8", newline="\n") as f:
    f.write(out)
print("wrote 404.html", len(out))
