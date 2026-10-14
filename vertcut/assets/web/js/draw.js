// Мелочь, из которой собирается разметка.
//
// Никаких шаблонов строкой и никакого innerHTML с чужим текстом:
// в названиях роликов и в тексте фраз бывают угловые скобки и
// амперсанды, а текст фразы приходит из расшифровки чужого видео.
// Собранный из строк субтитр однажды сломал бы вёрстку молча.

export function эл(имя, свойства = {}, дети = []) {
  const у = document.createElement(имя);
  for (const [ключ, значение] of Object.entries(свойства)) {
    if (значение === null || значение === undefined || значение === false) continue;
    if (ключ === 'класс') у.className = значение;
    else if (ключ === 'текст') у.textContent = значение;
    else if (ключ === 'стиль') Object.assign(у.style, значение);
    else if (ключ === 'на') for (const [что, дело] of Object.entries(значение)) у.addEventListener(что, дело);
    else if (ключ === 'свойства') Object.assign(у, значение);
    else у.setAttribute(ключ, значение === true ? '' : значение);
  }
  for (const дитя of дети.flat()) {
    if (дитя === null || дитя === undefined || дитя === false) continue;
    у.append(типично(дитя));
  }
  return у;
}

function типично(что) {
  return что instanceof Node ? что : document.createTextNode(String(что));
}

// Числа — моношириной с табличными цифрами. Правило 5 пакета дизайна:
// иначе столбцы дрожат.
export function моно(текст, класс = '') {
  return эл('span', { класс: ('vc-num ' + класс).trim(), текст });
}

// Галочка рисуется линией, а не набирается знаком: знака «✓» нет
// ни в одном из трёх шрифтов экрана, и браузер брал бы его из
// системного — то есть на чужой машине она выглядела бы чужой.
export function галка() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 12 12');
  svg.setAttribute('class', 'в-галка');
  svg.setAttribute('aria-hidden', 'true');
  const путь = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  путь.setAttribute('d', 'M1.8 6.4 L4.5 9.1 L10.2 3.1');
  svg.append(путь);
  return svg;
}

// Стрелка списка — линией, как и галка, и по той же причине: знака
// «⌄» нет ни в одном из трёх шрифтов экрана, и браузер брал бы его
// из системного. На чужой машине он выглядел бы чужим, а тут он
// стоит в поле, которое человек видит первым.
export function стрелка(класс = '') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 12 12');
  svg.setAttribute('class', ('в-стрелка ' + класс).trim());
  svg.setAttribute('aria-hidden', 'true');
  const путь = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  путь.setAttribute('d', 'M2.5 4.5 L6 8 L9.5 4.5');
  svg.append(путь);
  return svg;
}

// Карандаш — пометка «это правится по щелчку». Рисуется линиями,
// как галка и стрелка, и по той же причине: знака «✎» нет ни в одном
// из трёх шрифтов экрана, и браузер брал бы его из системного — то
// есть на чужой машине он выглядел бы чужим.
//
// Он подсказка, а не кнопка: своего щелчка у него нет, работает
// щелчок по всей строке. `aria-hidden` поэтому стоит — читалке он
// сказал бы «графика» и ничего больше.
export function карандаш(класс = '') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 14 14');
  svg.setAttribute('class', ('в-карандаш ' + класс).trim());
  svg.setAttribute('aria-hidden', 'true');
  // Тело карандаша прямоугольником по диагонали, острие — треугольником
  // на его конце, поперечина — ободок у тупого конца.
  // Поперечина отступает от тупого конца на 1.1, а не на единицу:
  // при единице её вторая точка попадает в подстроку, которую заслон
  // «одно число — одно место» узнаёт как цену сборки. Он прав, что
  // смотрит на подстроку: число в разметке экрана и должно быть
  // поводом посмотреть.
  for (const d of ['M2.2 11.8 L2.9 9.3 L9.7 2.5 L11.5 4.3 L4.7 11.1 Z',
                   'M8.6 3.6 L10.4 5.4']) {
    const путь = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    путь.setAttribute('d', d);
    svg.append(путь);
  }
  return svg;
}

export function точка(класс = '') {
  return эл('span', { класс: ('vc-dot ' + класс).trim() });
}

export function растяжка() {
  return эл('span', { класс: 'в-растяжка' });
}

// Заменить содержимое узла целиком. Отдельной функцией, потому что
// «сначала очистить, потом добавить» в двух местах однажды станет
// «добавить, забыв очистить» — и на экране будет два списка подряд.
export function положить(куда, что) {
  куда.replaceChildren(...[что].flat().filter(Boolean));
  return куда;
}
