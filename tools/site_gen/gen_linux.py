# -*- coding: utf-8 -*-
"""Linux documentation page (L-09). Run: python gen_linux.py  (writes docs/install-linux.html into SITE_OUT)."""
from common import *

STATUS = ('<div class="note"><p><strong>Предварительная сборка.</strong> Пакеты для Astra Linux и Альт опубликованы как предварительные: '
          'они проверены в тестовой среде, но <strong>совместимость с этими ОС производителями ОС пока не подтверждена</strong>. '
          'Для постоянной работы с персональными данными пользуйтесь версией для Windows, пока подтверждения не получены. %s</p></div>'
          % TODO("реквизиты сертификатов совместимости после их получения"))

_ROW = ('<tr><td>%s</td><td><a href="/download.php?f=%s" download="%s" '
        'onclick="ym(110179627,&#39;reachGoal&#39;,&#39;download_%s&#39;)">%s</a></td>'
        '<td>≈ %s МБ</td><td><code>%s</code></td></tr>')
ROWS = "\n".join(
    _ROW % (name.split(" (")[0], key, fname, key.replace("-", "_"), fname, size, sha)
    for key, fname, size, sha, name in LINUX_FILES)

PKG = "normaot-reestr"
page("docs/install-linux.html", "Установка и эксплуатация в Linux",
 "Установка и эксплуатация программы «Норма ОТ: Реестр обучения» в Linux (Astra Linux, Альт): требования, пакеты, проверка, мастер-ключ, данные, сеть.",
 "Документация · Linux", "Установка в <span class=\"mark\">Linux</span>",
 "Как установить, проверить и запустить программу в Astra Linux и Альт, как защищён мастер-ключ и где лежат данные.",
 '<p class="doc-meta">Версия программы %s · правообладатель: Кривоносов Д.А. · normaot.ru</p>\n%s' % (VER, STATUS) + '''
<div class="toc"><ol>
 <li><a href="#req">Требования</a></li><li><a href="#get">Пакеты и проверка</a></li>
 <li><a href="#install">Установка</a></li><li><a href="#first">Первый запуск и мастер-ключ</a></li>
 <li><a href="#data">Где хранятся данные</a></li><li><a href="#net">Сеть, прокси, сертификаты</a></li>
 <li><a href="#update">Обновление</a></li><li><a href="#remove">Удаление</a></li>
 <li><a href="#diff">Отличия от версии для Windows</a></li><li><a href="#trouble">Неисправности</a></li>
</ol></div>

<h2 id="req">1. Требования</h2>
<table>
<tr><td>Операционная система</td><td>Astra Linux (на базе Debian 12 и новее) или Альт (Одиннадцатая платформа), 64-разрядная (x86-64). %s</td></tr>
<tr><td>Библиотеки ОС</td><td>glibc 2.34 или новее; libstdc++ из GCC 11 или новее. Графические библиотеки Qt (xcb, OpenGL/EGL, fontconfig, D-Bus) подтягиваются зависимостями пакета</td></tr>
<tr><td>Графическая среда</td><td>X11 или Wayland (через XWayland)</td></tr>
<tr><td>Связка ключей</td><td>желательно запущенный Secret Service (gnome-keyring или KWallet): тогда мастер-ключ хранится в нём; иначе программа попросит парольную фразу</td></tr>
<tr><td>Шрифты</td><td>для печати протоколов DOCX рекомендуется метрический аналог Times New Roman (Liberation Serif, PT Astra Serif)</td></tr>
<tr><td>Место на диске</td><td>пакет ≈ 65–85 МБ; установленная программа ≈ 215 МБ; плюс место под данные</td></tr>
<tr><td>Python и прочее ПО</td><td>не требуется (интерпретатор и библиотеки входят в пакет)</td></tr>
<tr><td>Сеть</td><td>только для обмена с реестром Минтруда: доступ к <code>edu.rosmintrud.ru</code></td></tr>
</table>

<h2 id="get">2. Пакеты и проверка</h2>
<table>
<tr><th>ОС</th><th>Файл (кнопка загрузки)</th><th>Размер</th><th>SHA-256</th></tr>
%s
</table>
<p>Для каждого файла рядом лежит файл <code>.sha256</code>. Проверьте контрольную сумму до установки:</p>
<pre><code>sha256sum -c normaot-reestr_%s_amd64.deb.sha256</code></pre>
<p>Подпись GPG (файл <code>.asc</code>) для предварительной сборки не публикуется: сверяйте контрольную сумму SHA-256 со значением в таблице выше.</p>

<h2 id="install">3. Установка</h2>
<p>Astra Linux:</p>
<pre><code>sudo apt install ./normaot-reestr_%s_amd64.deb</code></pre>
<p>Альт:</p>
<pre><code>sudo apt-get install ./normaot-reestr-%s-alt1.x86_64.rpm</code></pre>
<p>Менеджер пакетов сам доустановит нужные библиотеки. Программа ставится в <code>/opt/normaot-reestr</code>, команда запуска <code>normaot-reestr</code>, пункт «Норма ОТ: Реестр обучения» появляется в меню (категория «Офис»).</p>
<p>Из архива <code>tar.gz</code>: распакуйте, скопируйте каталог в <code>/opt/normaot-reestr</code>, ярлык <code>normaot-reestr.desktop</code> — в <code>/usr/share/applications</code>, значок — в <code>/usr/share/pixmaps</code> (то же описано в файле <code>INSTALL.txt</code> внутри архива). Системные библиотеки Qt в этом случае ставятся вручную.</p>
<div class="note"><p>В Astra Linux Special Edition с включённой замкнутой программной средой (ЗПС) запуск файлов, не подписанных ключом, может быть запрещён. %s</p></div>

<h2 id="first">4. Первый запуск и мастер-ключ</h2>
<ol>
  <li>Если в сеансе работает Secret Service, ключ шифрования сохраняется в связке ключей пользователя; в файле <code>master.key</code> лежит только метка, а не сам ключ. Парольная фраза не запрашивается, при повторных запусках ключ берётся из связки автоматически.</li>
  <li>Если связки ключей нет, программа при первом запуске просит <strong>придумать парольную фразу</strong> (с повтором). Ключ шифруется ею (PBKDF2-HMAC-SHA256, 600 000 итераций) и записывается в <code>master.key</code>; при каждом запуске фразу нужно вводить. Потерянную фразу восстановить нельзя.</li>
  <li>Открытый ключ на диск не записывается ни в одном из вариантов. Дополнительную парольную фразу (второй слой) можно задать в окне «Безопасность», как и в Windows.</li>
  <li>Если связка ключей заблокирована или недоступна, программа сообщает об ошибке и <strong>не создаёт новый ключ</strong>: данные остаются прежними, нужно разблокировать связку и запустить программу снова.</li>
  <li>Ключ привязан к ОС и пользователю: файл <code>master.key</code> и резервные копии ключа из Windows или другой машины в Linux не подходят.</li>
</ol>

<h2 id="data">5. Где хранятся данные</h2>
<table>
<tr><td>Данные программы</td><td><code>~/.local/share/NormaOT</code> (или <code>$XDG_DATA_HOME/NormaOT</code>): база SQLite, настройки, мастер-ключ, журнал аудита; каталог доступен только владельцу (права 700), файл ключа — 600</td></tr>
<tr><td>Журналы работы</td><td><code>~/.local/share/NormaOT/log</code></td></tr>
<tr><td>Дополнительные организации</td><td><code>~/.local/share/NormaOT/orgs/&lt;идентификатор&gt;</code></td></tr>
<tr><td>Отметка заставки «Поддержите проект»</td><td><code>~/.config/NormaOT/support_state</code> (только дата)</td></tr>
<tr><td>Временные файлы</td><td>каталог в <code>$XDG_RUNTIME_DIR</code> с правами 700, удаляется при закрытии программы</td></tr>
</table>
<p>Рядом с программой (в <code>/opt/normaot-reestr</code>) ничего не записывается. Резервные копии базы создаются с ротацией (не более 5) и шифруются паролем, производным от мастер-ключа. Копируйте каталог данных средствами организации под тем же пользователем.</p>

<h2 id="net">6. Сеть, прокси, сертификаты</h2>
<ul>
  <li>Режим прокси «Авто (системные)» берёт адрес из переменных окружения <code>https_proxy</code> / <code>http_proxy</code>; адреса из <code>no_proxy</code> (в том числе <code>edu.rosmintrud.ru</code>) исключаются. Режимы «Без прокси» и «Вручную» работают как в Windows.</li>
  <li>Авторизация Negotiate/Kerberos в Linux не поддерживается (флажок скрыт); для прокси с логином и паролем используйте ручной режим.</li>
  <li>Проверка TLS-сертификата сервера включена по умолчанию и использует хранилище сертификатов ОС. Если центра сертификации сервера (например, российского УЦ) нет в хранилище, добавьте его средствами ОС либо укажите файл с корневыми сертификатами в параметре <code>ca_file</code> файла <code>~/.local/share/NormaOT/proxy_settings.json</code>.</li>
  <li>Транспорт: библиотеки <code>requests</code> и <code>urllib</code> (WinHTTP в Linux нет).</li>
</ul>

<h2 id="update">7. Обновление</h2>
<p>Программа не обновляется автоматически и не управляется удалённо. Новую версию устанавливают так же, как первую (пункт 3); данные подхватываются из каталога данных. Перед обновлением сделайте копию <code>~/.local/share/NormaOT</code>. Узнать о новых версиях можно на странице «<a href="/changelog.html">История версий</a>».</p>

<h2 id="remove">8. Удаление</h2>
<pre><code>sudo apt remove normaot-reestr          # Astra Linux
sudo apt-get remove normaot-reestr      # Альт</code></pre>
<p>Данные пользователя при этом остаются. Чтобы удалить и их, выберите в программе «Настройки и темы → Безопасность → Удалить все данные приложения» (нужно ввести слово «УДАЛИТЬ»): удаляются все файлы каталога данных, а мастер-ключ <strong>удаляется и из связки ключей</strong>. Восстановить данные после этого нельзя.</p>

<h2 id="diff">9. Отличия от версии для Windows</h2>
<table>
<tr><th>Область</th><th>Windows</th><th>Linux</th></tr>
<tr><td>Защита мастер-ключа</td><td>Windows DPAPI</td><td>Secret Service или парольная фраза</td></tr>
<tr><td>Данные</td><td><code>%%APPDATA%%\\NormaOT</code></td><td><code>~/.local/share/NormaOT</code></td></tr>
<tr><td>Установка</td><td>распаковать архив</td><td>пакет .deb / .rpm или архив</td></tr>
<tr><td>Подпись файла</td><td>Authenticode (самоподписанный сертификат)</td><td>SHA-256 и, если опубликована, подпись GPG</td></tr>
<tr><td>Негоциация прокси (Negotiate)</td><td>есть</td><td>нет</td></tr>
<tr><td>Отправка отчёта об ошибке</td><td>Outlook или почтовый клиент по умолчанию</td><td>почтовый клиент по умолчанию (mailto)</td></tr>
</table>
<p>Остальные функции (импорт и экспорт, отправка в реестр Минтруда, журнал, протоколы, сводка, несколько организаций) работают одинаково.</p>

<h2 id="trouble">10. Неисправности</h2>
<ul>
  <li><strong>«Could not load the Qt platform plugin "xcb"»</strong> — не хватает библиотек Qt. При установке из пакета их ставит менеджер пакетов; при установке из архива поставьте <code>libxcb-icccm4</code>, <code>libxcb-image0</code>, <code>libxcb-keysyms1</code>, <code>libxcb-render-util0</code>, <code>libxcb-xkb1</code>, <code>libxkbcommon-x11-0</code> и их аналоги в Альт.</li>
  <li><strong>Программа просит парольную фразу, хотя связка ключей есть</strong> — Secret Service не запущен в этом сеансе (например, вход по SSH или без графической сессии). Запустите программу в графическом сеансе или пользуйтесь парольной фразой.</li>
  <li><strong>Ошибка проверки сертификата сервера</strong> — см. п. 6 (корневой сертификат, <code>ca_file</code>).</li>
  <li><strong>Протокол DOCX выглядит иначе, чем в Word</strong> — установите метрический аналог Times New Roman (Liberation Serif или PT Astra Serif).</li>
  <li>Если проблема осталась — напишите в <a href="/contacts.html">техническую поддержку</a>: версия программы, версия ОС (<code>cat /etc/os-release</code>), шаги воспроизведения, без персональных данных.</li>
</ul>
''' % (TODO("точные редакции и релизы ОС после выбора и испытаний"),
       ROWS,
       VER,
       VER, VER,
       TODO("порядок подписи ключами Ready for Astra после выяснения у производителя ОС")), doc_tools=True)
