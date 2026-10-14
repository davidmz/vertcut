// Приём видео: два входа, и они стоят разного.
//
// **Разницу человек узнаёт ДО того, как заплатит.** Браузер отдаёт
// содержимое файла, а не путь — значит брошенный в окно подкаст
// копируется целиком и занимает на диске второй раз. Молча удвоить
// три гигабайта — плохой сюрприз, поэтому сперва полоса с числами,
// и только потом копирование.
//
// Второй вход — системный диалог, который открывает сам сервис.
// Там копии нет вовсе: видео остаётся лежать где лежало.

import { сказать, сказать_беду, убрать_полосы, эл, моно } from './shell.js';
import * as связь from './api.js';
import * as слова from './words.js';
import * as адрес from './route.js';

// Куда идти, когда видео принято. Ставится снаружи, чтобы приём
// не знал ничего про устройство экранов.
export let принято = (слаг) => { адрес.идти('videos'); };

export function куда_после(дело) { принято = дело; }

// ── Бросили в окно ────────────────────────────────────────────────────

export function ловить_броски(узел) {
  const гасить = (е) => { е.preventDefault(); е.stopPropagation(); };
  for (const что of ['dragenter', 'dragover']) {
    узел.addEventListener(что, (е) => {
      гасить(е);
      узел.dataset.ловим = '1';
    });
  }
  for (const что of ['dragleave', 'drop']) {
    узел.addEventListener(что, (е) => {
      гасить(е);
      delete узел.dataset.ловим;
    });
  }
  узел.addEventListener('drop', async (е) => {
    const файл = (е.dataTransfer?.files || [])[0];
    if (файл) await спросить_и_принять(файл);
  });
}

// Полоса-вопрос перед копированием. Правило 3 пакета: спрашиваем
// полосой во всю ширину, никогда модальным окном.
async function спросить_и_принять(файл) {
  let место;
  try {
    место = await связь.взять('место', { имя: файл.name, размер: файл.size });
  } catch (беда) { return сказать_беду(беда); }

  убрать_полосы();

  if (место.уже_лежит) {
    // Тот же файл уже во «Входящих» — копировать три гигабайта
    // повторно незачем.
    return await по_пути(место.уже_лежит);
  }
  if (!место.хватит) {
    return сказать({
      вид: 'bad',
      что: `Not enough space: the file is ${слова.гигабайт(место.размер)}, ` +
           `${слова.гигабайт(место.свободно)} free.`,
      делать: `Vertcut also needs ${слова.гигабайт(место.запас)} to spare — ` +
              'analysis keeps the audio, a smaller copy and frames next ' +
              'to it. Use Choose file instead: then nothing is copied.',
    });
  }

  const что = место.занято_другим
    ? `Inbox already has a different file named “${место.имя}”.`
    : `Copy “${место.имя}” into the Vertcut folder?`;
  const делать = место.занято_другим
    ? 'Rename one of them — or use Choose file for this one, ' +
      'then no copy is needed.'
    : `${слова.гигабайт(место.размер)} · this takes that much more disk ` +
      `space, ${слова.гигабайт(место.свободно)} free now. ` +
      'Use Choose file to avoid the copy.';

  const действия = место.занято_другим ? [] : [
    эл('button', {
      класс: 'vc-btn vc-btn--sm vc-btn--primary',
      текст: 'Copy',
      на: { click: () => { убрать_полосы(); лить(файл); } },
    }),
    эл('button', {
      класс: 'vc-btn vc-btn--sm', текст: 'Cancel',
      на: { click: убрать_полосы },
    }),
  ];
  сказать({ вид: место.занято_другим ? 'bad' : 'ask', что, делать, действия });
  if (!место.знакомое) {
    сказать({
      вид: 'warn',
      что: `Vertcut does not know the “${место.имя.replace(/^.*\./, '.')}” file type.`,
      делать: 'You can copy it, but analysis will probably refuse it: ' +
              'Vertcut looks at the video itself, not at its name.',
    });
  }
}

// Само копирование. Идёт через XHR, а не через fetch, и это
// не старомодность: только XHR умеет сказать, сколько байт уже ушло.
// Копирование трёх гигабайт идёт минуту, и минута без единого знака
// о том, что что-то происходит, читается как «сервис завис».
function лить(файл) {
  const полоса = ход(файл);
  const запрос = new XMLHttpRequest();
  запрос.open('POST', связь.адрес('бросить', { имя: файл.name }));
  let смотрел = null;
  запрос.upload.addEventListener('progress', (е) => {
    if (е.lengthComputable) полоса.двигать(е.loaded / е.total);
  });
  // Байты ушли, но ответа ещё нет: сервис в это время считает
  // отпечаток. Полоса копирования уже неправда, а тишина — тем более.
  запрос.upload.addEventListener('load', () => {
    полоса.убрать();
    смотрел = смотрю(файл.name);
  });
  запрос.addEventListener('load', () => {
    полоса.убрать();
    смотрел?.remove();
    let это = {};
    try { это = JSON.parse(запрос.responseText); } catch (_) { /* ниже */ }
    if (запрос.status >= 400 || !это.слаг) {
      return сказать({
        вид: 'bad',
        что: это.беда || `Vertcut did not accept the file (${запрос.status}).`,
        делать: это.подсказка || '',
      });
    }
    принято(это.слаг);
  });
  запрос.addEventListener('error', () => {
    полоса.убрать();
    смотрел?.remove();
    сказать({ вид: 'bad', что: 'Copying was interrupted.',
              делать: 'Drop the file again — the partial copy has been removed.' });
  });
  запрос.send(файл);
}

function ход(файл) {
  const линия = эл('i', { стиль: { width: '0%' } });
  const цифра = моно('0%');
  const полоса = сказать({
    вид: 'ask',
    что: `Copying “${файл.name}” — ${слова.гигабайт(файл.size)}`,
    делать: 'Do not close this tab yet: the copy goes through it.',
    действия: [цифра],
  });
  полоса.querySelector('.vc-bar__what').append(
    эл('div', { класс: 'vc-progress', стиль: { marginTop: '6px' } }, [линия]));
  return {
    двигать(доля) {
      линия.style.width = `${Math.round(доля * 100)}%`;
      цифра.textContent = `${Math.round(доля * 100)}%`;
    },
    убрать() { полоса.remove(); },
  };
}

// ── Опознание ─────────────────────────────────────────────────────────
//
// Между нажатием и ответом проходит около десяти секунд: сервис
// считает отпечаток файла, а трёхгигабайтный файл столько и читается.
// Молчать это время нельзя — человек решит, что кнопка не сработала,
// и нажмёт ещё раз.

function смотрю(имя) {
  return сказать({
    вид: 'ask',
    что: имя ? `Reading “${имя}”…` : 'Opening the file picker…',
    делать: имя
      ? 'Fingerprinting the file — about ten seconds for 3 GB. ' +
        'It lets Vertcut notice if the file is later swapped for ' +
        'another one with the same name.'
      : 'The picker will open on top of the browser.',
  });
}

// ── Выбрали на диске ──────────────────────────────────────────────────

export async function выбрать_на_диске() {
  убрать_полосы();
  const полоса = смотрю(null);
  try {
    const это = await связь.послать('выбрать');
    if (это.передумал) return;      // «Отмена» — это не отказ
    принято(это.слаг);
  } catch (беда) {
    сказать_беду(беда);
  } finally {
    полоса.remove();
  }
}

export async function по_пути(путь) {
  убрать_полосы();
  const полоса = смотрю(путь.replace(/^.*\//, ''));
  try {
    const это = await связь.послать('принять-путь', { путь });
    принято(это.слаг);
  } catch (беда) {
    сказать_беду(беда);
  } finally {
    полоса.remove();
  }
}
