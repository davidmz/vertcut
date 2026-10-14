// Vertcut.exe — то, по чему человек щёлкает на Windows.
//
// РАБОТА У НЕГО ОДНА: позвать `install\launcher.ps1` и уйти. Ни установки,
// ни сервиса, ни адресов здесь нет — всё это в ярлыке PowerShell и в питоне,
// тех же самых, что звал `Vertcut.cmd`. Второй правды о том, как сервис
// поднимается, этот файл не заводит.
//
// ЗАЧЕМ ОН, ЕСЛИ `Vertcut.cmd` РАБОТАЛ. Работал, но выглядел служебным
// файлом: Windows прячет окончание, и человек видел «Vertcut» с серой
// шестерёнкой и подписью «Сценарий Windows». Программой это не читается,
// и нажимать на это не хочется. Заодно пропало окно консоли, которое
// `.cmd` показывал на долю секунды: это программа без окна вовсе.
//
// СОБИРАЕТСЯ компилятором, который лежит на всякой Windows вместе
// с .NET Framework (`build-launcher.py`), — новой зависимости нет.
// Отсюда и язык: C# 5, без новых слов — компилятор там старый.
//
// ФАЙЛ ЛЕЖИТ С МЕТКОЙ UTF-8, И КОМПИЛЯТОРУ ЭТО ЕЩЁ И СКАЗАНО
// (`/codepage:65001`). Без того и другого он прочёл бы русские слова
// кодировкой системы, и человек получил бы окно с мусором. Сверяется
// проверкой; имена в коде — латиницей.

using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Vertcut
{
    static int Main()
    {
        string here = AppDomain.CurrentDomain.BaseDirectory;
        string launcher = Path.Combine(Path.Combine(here, "install"), "launcher.ps1");

        // ПЕРЕНЕСЛИ ОДИН EXE БЕЗ ПАПКИ. Самое частое, что с ним сделают:
        // вытащат на Рабочий стол, как вытаскивают всякую программу.
        // Молча не запуститься значит оставить человека гадать; говорим,
        // что не так и как поправить.
        if (!File.Exists(launcher))
        {
            MessageBox.Show(
                "Vertcut.exe has to stay in its own folder, next to the install folder.\n\n" +
                "Put it back there, or open the Vertcut.exe that is in the Vertcut folder.",
                "Vertcut", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return 1;
        }

        // Те же слова, что стояли в `Vertcut.cmd`, — один в один.
        ProcessStartInfo start = new ProcessStartInfo();
        start.FileName = "powershell.exe";
        start.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \""
                          + launcher + "\"";
        start.WorkingDirectory = here;
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        try
        {
            Process.Start(start);
        }
        catch (Exception error)
        {
            MessageBox.Show(
                "Couldn't start PowerShell: " + error.Message,
                "Vertcut", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }
}
