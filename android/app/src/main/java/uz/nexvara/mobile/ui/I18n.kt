package uz.nexvara.mobile.ui

import androidx.compose.material3.LocalTextStyle
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow

/**
 * Interface language. Uzbek (Latin) is the main language; Russian is a translation of the
 * screens' fixed words. Ready commands stay Uzbek on purpose — the PC understands Uzbek
 * commands — and so do the PC's own replies.
 *
 * Every `Text(...)` in this package goes through [tr] (this declaration shadows Material's
 * `Text` for the files of the package).
 */
object Lang {
    var ru by mutableStateOf(false)
}

fun tr(s: String): String {
    if (!Lang.ru) return s
    RU[s]?.let { return it }
    for ((rx, out) in PATTERNS) {
        val m = rx.matchEntire(s) ?: continue
        return out(m.groupValues)
    }
    return s
}

/** Sentences with numbers in them. */
private val PATTERNS: List<Pair<Regex, (List<String>) -> String>> = listOf(
    Regex("qoldi (.+)") to { g -> "осталось ${g[1]}" },
    Regex("(\\d+) ta panel") to { g -> "панелей: ${g[1]}" },
    Regex("(\\d+) ta jarayon") to { g -> "процессов: ${g[1]}" },
    Regex("(\\d+) ta qoida") to { g -> "правил: ${g[1]}" },
    Regex("(\\d+) ta eslatma") to { g -> "заметок: ${g[1]}" },
    Regex("(\\d+) ta o‘quvchi") to { g -> "учеников: ${g[1]}" },
    Regex("(\\d+) ta maydon") to { g -> "полей: ${g[1]}" },
    Regex("(\\d+) ta") to { g -> g[1] },
    Regex("Oylik limit (.+) · AI yoqilgan") to { g -> "Месячный лимит ${g[1]} · AI включён" },
    Regex("Oylik limit (.+) · AI o‘chiq") to { g -> "Месячный лимит ${g[1]} · AI выключен" },
    Regex("Bugun: (.+)") to { g -> "Сегодня: ${g[1]}" },
    Regex("Oxirgi: (.+) · shifrlangan") to { g -> "Последняя: ${g[1]} · зашифровано" },
    Regex("(\\d+) savol · (\\d+) variant · (\\d+) ta tekshirildi(.*)") to { g -> "${g[1]} вопр. · ${g[2]} вар. · проверено: ${g[3]}${g[4].replace(" · kalit yo‘q", " · нет ключа")}" },
    Regex("(\\d+)-sinf") to { g -> "${g[1]} класс" },
)

@Composable
fun Text(
    text: String, modifier: Modifier = Modifier, color: Color = Color.Unspecified, style: TextStyle = LocalTextStyle.current,
    fontWeight: FontWeight? = null, maxLines: Int = Int.MAX_VALUE, overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign? = null,
) = androidx.compose.material3.Text(tr(text), modifier, color = color, fontWeight = fontWeight, textAlign = textAlign,
    overflow = overflow, maxLines = maxLines, style = style)

private val RU: Map<String, String> = mapOf(
    // navigation and screens
    "Bosh sahifa" to "Главная", "Suhbat" to "Чат", "Vazifalar" to "Задачи", "Bo‘limlar" to "Разделы",
    "AI suhbat" to "AI-чат", "Office yordamchisi" to "Помощник Office", "Darsliklar va testlar" to "Учебники и тесты",
    "Fayllar" to "Файлы", "NEXVARA BI" to "NEXVARA BI", "Ish jarayonlari" to "Рабочие процессы",
    "NEXVARA’ga o‘rgatish" to "Обучение NEXVARA", "Xotira" to "Память", "AI balans va xarajatlar" to "Баланс и расходы AI",
    "Kompyuterlar" to "Компьютеры", "Sozlamalar" to "Настройки", "Kompyuter ekrani" to "Экран компьютера",
    "Tayyor buyruqlar" to "Готовые команды", "Javob varaqalari" to "Бланки ответов", "Sinf jurnali" to "Классный журнал",
    "Hujjat shablonlari" to "Шаблоны документов", "Dars jadvali" to "Расписание уроков", "Majlis yozuvi" to "Запись совещания",
    "Ko‘rish" to "Просмотр", "Windows NEXVARA’ning barcha bo‘limlari" to "Все разделы NEXVARA для Windows",
    // home
    "Bugun nima qilamiz?" to "Что делаем сегодня?",
    "Buyruq yozing yoki ayting — kompyuter ekranida bajariladi." to "Напишите или скажите команду — она выполнится на экране компьютера.",
    "Yozish" to "Написать", "Gapirish" to "Сказать", "Tezkor amallar" to "Быстрые действия", "Office" to "Office",
    "Test tuzish" to "Составить тест", "BI panellar" to "Панели BI", "Ekran" to "Экран", "Chizma" to "Чертёж",
    "Tayyor buyruq" to "Команды", "Batafsil" to "Подробнее", "Oxirgi vazifalar" to "Последние задачи", "Hammasi" to "Все",
    "Hali vazifa yo‘q. Suhbatda buyruq bering." to "Задач пока нет. Дайте команду в чате.", "NEXVARA holati" to "Состояние NEXVARA",
    "Ulangan" to "Подключён", "Aloqa yo‘q" to "Нет связи", "Tekshirilmoqda" to "Проверка", "Bu oy" to "Этот месяц",
    "Bugun" to "Сегодня", "Bugungi darslar" to "Уроки сегодня", "Jadval" to "Расписание", "Kompyuterni yoqish" to "Включить компьютер",
    "Yuklanmoqda…" to "Загрузка…",
    // pairing and lock
    "NEXVARA’ga xush kelibsiz" to "Добро пожаловать в NEXVARA", "QR kodni skanerlash" to "Сканировать QR-код",
    "yoki havolani joylang" to "или вставьте ссылку", "Bog‘lash" to "Подключить", "← Orqaga" to "← Назад",
    "NEXVARA qulflangan" to "NEXVARA заблокирован", "Barmoq izi, yuz yoki telefon PIN-kodi bilan oching" to "Откройте отпечатком, лицом или PIN-кодом",
    "Ochish" to "Открыть",
    // chat and tasks
    "Nima qilay?" to "Что сделать?", "Masalan quyidagilardan birini tanlang yoki o‘zingiz yozing." to "Выберите пример или напишите сами.",
    "Tasdiq kerak" to "Нужно подтверждение", "Ha, davom et" to "Да, продолжить", "Yo‘q" to "Нет", "Fonda bajar" to "В фоне",
    "Buyruq yozing…" to "Напишите команду…", "Fayl" to "Файл", "PDF" to "PDF", "Rasm" to "Фото", "Kamera" to "Камера",
    "Tayyor buyruqlar: o‘qituvchi, ofis, hujjat, chizma" to "Готовые команды: учитель, офис, документы, чертежи",
    "Kompyuterdagi jarayonlar jonli yangilanadi" to "Процессы на компьютере обновляются вживую", "Bajarilmoqda" to "Выполняется",
    "Tayyor" to "Готово", "Xato/bekor" to "Ошибка/отмена", "Vazifa yo‘q" to "Задач нет",
    "Suhbatda buyruq bering — jarayon shu yerda ko‘rinadi." to "Дайте команду в чате — процесс появится здесь.",
    "Pauza" to "Пауза", "Davom ettirish" to "Продолжить", "Bekor qilish" to "Отмена", "Chizmani tuzatish" to "Исправить чертёж",
    "Kutilmoqda" to "Ожидает", "Pauzada" to "На паузе", "Bajarildi" to "Выполнено", "Xatolik" to "Ошибка",
    "Bekor qilindi" to "Отменено", "Pauza kutilmoqda" to "Ждёт паузы",
    // office, library, files
    "Buyruq bering" to "Дайте команду", "Bajarish" to "Выполнить", "Namuna buyruqlar" to "Примеры команд", "Bir bosishda" to "Одним нажатием",
    "Excel jadval" to "Таблица Excel", "Excel dashboard" to "Дашборд Excel", "Word hisobot" to "Отчёт Word",
    "PowerPoint taqdimot" to "Презентация PowerPoint", "Chizib berish" to "Начертить", "Suratga olish" to "Сфотографировать",
    "Galereyadan" to "Из галереи", "Sinf" to "Класс", "Fan" to "Предмет", "Mavzu (ixtiyoriy)" to "Тема (необязательно)",
    "Variantlar" to "Варианты", "AI yordamida" to "С помощью AI", "Test tuzish (Word kompyuterda)" to "Составить тест (Word на ПК)",
    "Mavzu matni" to "Текст темы", "Taqdimot" to "Презентация", "Dars rejasi (AI) →" to "План урока (AI) →", "Darsliklar" to "Учебники",
    "Darslik yo‘q" to "Учебников нет", "Kompyuterga yuborish" to "Отправить на компьютер", "Tayyor natijalar" to "Готовые результаты",
    "Hali natija yo‘q" to "Результатов пока нет", "Kompyuterdan qidirish" to "Поиск на компьютере", "masalan: hisobot" to "например: отчёт",
    "Kompyuterda ochish" to "Открыть на ПК", "Telefonga" to "На телефон", "Buyruq" to "Команда", "Excel" to "Excel", "Word" to "Word",
    "PowerPoint" to "PowerPoint", "Rasmdan matn" to "Текст с фото", "Avto" to "Авто", "Lotin" to "Латиница", "Kirill" to "Кириллица",
    "Nusxa" to "Копировать", "Test (AI)" to "Тест (AI)", "Konspekt (AI)" to "Конспект (AI)", "Hujjatni skanerlash" to "Сканировать документ",
    "Skanerlash → PDF" to "Сканировать → PDF", "Qo‘lyozma: AI bilan aniq o‘qish" to "Рукопись: точное чтение с AI",
    // BI, workflows, teach, memory
    "Kompyuter ekranida ham ochish" to "Открыть и на экране ПК", "Panel yo‘q" to "Панелей нет", "Suhbatda yaratish" to "Создать в чате",
    "Chat orqali boshqarish" to "Управление через чат", "Suhbatga o‘tish" to "Перейти в чат", "Ma’lumot yo‘q" to "Нет данных",
    "Hozir bajarilmoqda" to "Выполняется сейчас", "Tasdiqlash" to "Подтвердить", "Jarayonlar" to "Процессы", "Jarayon yo‘q" to "Процессов нет",
    "Ishga tushirish" to "Запустить", "Tahrirlash" to "Изменить", "Shablonlar" to "Шаблоны", "Jarayonni o‘chirish" to "Удалить процесс",
    "Nomi" to "Название", "Qadamlar (har qatorda bitta buyruq)" to "Шаги (по одной команде в строке)", "Qo‘lda" to "Вручную",
    "Har kuni" to "Каждый день", "Hafta kunlari" to "Дни недели", "Vaqt (SS:DD)" to "Время (ЧЧ:ММ)", "Saqlash" to "Сохранить",
    "Yangi qoida" to "Новое правило", "Tekshirish" to "Проверить", "Qoida yo‘q" to "Правил нет", "O‘chirish" to "Удалить",
    "Qoidani o‘chirish" to "Удалить правило", "Xotiradan qidirish…" to "Поиск в памяти…", "Eslatmalar" to "Заметки",
    "Hali eslatma yo‘q" to "Заметок пока нет", "Eslab qolish" to "Запомнить", "Matn" to "Текст", "Eslatmani o‘chirish" to "Удалить заметку",
    // AI spend
    "To‘ldirish" to "Пополнить", "Sarf" to "Расход", "Oxirgi so‘rovlar" to "Последние запросы",
    // PCs, Google, settings
    "Yana kompyuter qo‘shish" to "Добавить компьютер", "Tanlangan kompyuterdan chiqish" to "Выйти из выбранного компьютера",
    "Tanlangan kompyuterni yoqish" to "Включить выбранный компьютер", "Google hisobi" to "Аккаунт Google", "Kompyuter nomi" to "Имя компьютера",
    "Kompyuterdan chiqish" to "Выйти из компьютера", "Chiqish" to "Выйти", "Google bilan bog‘lash" to "Связать с Google",
    "Telefon faqat kompyuter egasining Google hisobi bilan bog‘lanadi." to "Телефон связывается только с аккаунтом Google владельца ПК.",
    "✓ Telefon va kompyuter bitta hisobda" to "✓ Телефон и компьютер в одном аккаунте", "Ko‘rinish" to "Вид",
    "Mavzu" to "Тема", "Tizim bo‘yicha" to "Как в системе", "Yorug‘" to "Светлая", "Qorong‘i" to "Тёмная", "Til" to "Язык",
    "Xavfsizlik va ovoz" to "Безопасность и голос", "Ilova qulfi" to "Блокировка приложения", "Ovozli suhbat" to "Голосовой чат",
    "Ovoz tili" to "Язык голоса", "Gapirganda qaysi tilda tanisin" to "На каком языке распознавать речь",
    "O‘zbekcha" to "Узбекский", "Ruscha" to "Русский", "Inglizcha" to "Английский", "Kompyuter" to "Компьютер",
    "Windows bilan birga ishga tushsin" to "Запускать вместе с Windows",
    "Kompyuter yoqilganda NEXVARA o‘zi ochiladi va telefon ulanadi" to "NEXVARA откроется при включении ПК, и телефон подключится",
    "Kompyuterni uyg‘otish (Wake-on-LAN)" to "Разбудить компьютер (Wake-on-LAN)", "Boshqa tarmoqdan ulanish" to "Подключение из другой сети",
    "Telefonga o‘rnatish" to "Установить на телефон", "Kompyuter uchun" to "Для компьютера", "Maxfiylik va xabarlar" to "Приватность и уведомления",
    "Ekran rasmini taqiqlash" to "Запретить скриншоты", "Skrinshot olinmaydi, «so‘nggi ilovalar»da ko‘rinmaydi" to "Скриншоты запрещены, не видно в «недавних»",
    "Ilova yopiq bo‘lsa ham xabar" to "Уведомления при закрытом приложении",
    "Har 15 daqiqada vazifalar tekshiriladi (kompyuter yoqiq bo‘lsa)" to "Задачи проверяются каждые 15 минут (если ПК включён)",
    "Sinxronlash (NEXVARA-SYNC)" to "Синхронизация (NEXVARA-SYNC)", "Hozir sinxronlash" to "Синхронизировать сейчас", "Google" to "Google",
    "Xavfsizlik" to "Безопасность", "Shifrlangan aloqa" to "Зашифрованная связь", "Token Android Keystore’da" to "Токен в Android Keystore",
    "Chat tarixi va navbat ham shifrlangan" to "История чата и очередь тоже зашифрованы", "Shaxsiy ma’lumotlar himoyasi" to "Защита личных данных",
    "AI’ga ketadigan har so‘rov kompyuterda yashiriladi" to "Каждый запрос к AI маскируется на компьютере",
    // ready commands screen (titles only — the command texts stay Uzbek)
    "Bosing — suhbatda tahrirlab yuborasiz" to "Нажмите — отредактируйте в чате и отправьте", "★ Sevimlilar" to "★ Избранное",
    "Oxirgi buyruqlar" to "Последние команды", "O‘qituvchi uchun" to "Для учителя", "Ofis ishlari" to "Офисная работа",
    "Hujjatlar (AI)" to "Документы (AI)", "Xotira va boshqalar" to "Память и другое", "Darslikdan test (bepul)" to "Тест из учебника (бесплатно)",
    "Mavzu matni darslikdan" to "Текст темы из учебника", "Mavzu bo‘yicha taqdimot" to "Презентация по теме", "AI bilan test" to "Тест с AI",
    "Dars rejasi (AI)" to "План урока (AI)", "Uyga vazifa va javoblar (AI)" to "Домашнее задание с ответами (AI)",
    "Ota-onalarga e’lon (AI)" to "Объявление для родителей (AI)", "Baholar jadvali" to "Таблица оценок", "Baholar dashboardi" to "Дашборд оценок",
    "Darslikdan savol (AI)" to "Вопрос по учебнику (AI)", "Excel hisobotni tozalash" to "Очистка отчёта Excel", "Saralash" to "Сортировка",
    "Savdo dashboardi" to "Дашборд продаж", "Word’ni PDF qilish" to "Word в PDF", "Shu faylni PDF qilish" to "Этот файл в PDF",
    "Fayl topish" to "Найти файл", "Fonda bajarish" to "Выполнить в фоне", "Ariza" to "Заявление", "Rasmiy xat" to "Официальное письмо",
    "Buyruq loyihasi" to "Проект приказа", "Tarjima" to "Перевод", "Qisqartirish" to "Сокращение", "Detal chizmasi" to "Чертёж детали",
    "Sxema" to "Схема", "Oxirgi chizmani tuzatish" to "Исправить последний чертёж", "Nimalarni bilasan" to "Что ты знаешь",
    "Teach qoidasi" to "Правило обучения", "Sinxronlash" to "Синхронизация",
    // teacher tools
    "Yangi varaqa" to "Новый бланк", "Nomi (masalan: 7-B fizika, 1-chorak)" to "Название (например: 7-Б физика, 1-я четверть)",
    "Savollar" to "Вопросы", "Nusxa soni" to "Кол-во копий", "To‘g‘ri javoblar (ixtiyoriy): ABCDA…" to "Правильные ответы (необязательно): ABCDA…",
    "Varaqa tayyorlash (kompyuterda chop etish)" to "Подготовить бланк (печать на ПК)", "Varaqalar" to "Бланки",
    "O‘quvchi (ixtiyoriy)" to "Ученик (необязательно)", "Suratga olib tekshirish" to "Сфотографировать и проверить", "Kalit" to "Ключ",
    "Varaqani ko‘rish" to "Посмотреть бланк", "To‘g‘ri javoblar" to "Правильные ответы", "Sinf yo‘q" to "Классов нет",
    "Fan (masalan: Fizika)" to "Предмет (например: Физика)", "O‘quvchilar yo‘q" to "Учеников нет", "Qo‘shish" to "Добавить",
    "← Sinflar" to "← Классы", "Yangi sinf" to "Новый класс", "Sinf nomi, masalan 7-B" to "Название класса, например 7-Б",
    "O‘quvchilar" to "Ученики", "Har qatorda bitta ism-familiya" to "По одному ФИО в строке", "Sinfni o‘chirish" to "Удалить класс",
    "Namuna bilan to‘ldirish" to "Заполнить примером", "Fonda (Word ko‘rinmaydi)" to "В фоне (Word не виден)", "Yaratish" to "Создать",
    "Eslatma darsdan oldin" to "Напоминание перед уроком", "Boshlanish (SS:DD)" to "Начало (ЧЧ:ММ)", "Dars: 7-B fizika" to "Урок: 7-Б физика",
    "Xona (ixtiyoriy)" to "Кабинет (необязательно)", "Bayonnoma (AI)" to "Протокол (AI)", "Kompyuterga matn" to "Текст на компьютер",
    "AI bilan tahrirlash" to "Исправить с AI", "Tozalash" to "Очистить", "Fayl tanlanmagan" to "Файл не выбран", "PDF ochilmadi" to "PDF не открылся",
    "Yozishni boshlash" to "Начать запись", "To‘xtatish" to "Остановить", "Hali hech narsa yozilmadi" to "Пока ничего не записано",
    "Kompyuterga yozish" to "Ввод на компьютер", "Kompyuter ekrani yuklanmoqda…" to "Загружается экран компьютера…",
    "NEXVARA’ga buyruq…" to "Команда для NEXVARA…", "Yopish" to "Закрыть",
    "Qoidalar" to "Правила", "Panellar" to "Панели", "Sinxron sozlanmagan" to "Синхронизация не настроена",
    "Kompyuterda Sozlamalar → Sinxronlash" to "На ПК: Настройки → Синхронизация", "ulangan" to "подключён",
    "kalit yo‘q" to "нет ключа", "Kalit kiritilmagan" to "Ключ не введён", "baho yo‘q" to "оценок нет",
    "Kompyuter bilan aloqa yo‘q — ulangach sarf va limitlar shu yerda ko‘rinadi" to "Нет связи с ПК — расходы и лимиты появятся после подключения",
    "Tinglayapman…" to "Слушаю…", "Gapirilganini matnga aylantiradi" to "Превращает речь в текст", "Boshqarish rejimi" to "Режим управления",
    "Faqat ko‘rish" to "Только просмотр", "To‘xtatilgan" to "Остановлено", "Buyruqlar kompyuterda bajariladi" to "Команды выполняются на ПК",
    "Ovozli suhbat yoqilgan" to "Голосовой чат включён", "Suhbatga" to "В чат", "Sevimlilarga" to "В избранное",
    "Kompyuterni boshqarish" to "Управление компьютером", "Darsdan oldin eslatma keladi (internetsiz)" to "Напоминание перед уроком (без интернета)",
    "To‘ldiring — Word kompyuterda yozadi (DOCX + PDF)" to "Заполните — Word напишет на ПК (DOCX + PDF)",
    "Telefondan baho qo‘ying — Excel jurnal kompyuterda" to "Ставьте оценки с телефона — журнал Excel на ПК",
    "Chop eting → o‘quvchilar bo‘yaydi → suratga oling → baho tayyor" to "Печать → ученики закрашивают → фото → оценка готова",
    "Galereyadan" to "Из галереи",
)
