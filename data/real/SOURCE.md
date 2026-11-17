# Tennessee Eastman Process — منبع داده واقعی

## منبع
- مخزن: https://github.com/camaramm/tennessee-eastman-profBraatz (شاخه master)
- فایل‌های خام (.dat): data/real/raw_tep/d00.dat .. d21.dat و d00_te.dat .. d21_te.dat
- مرجع علمی: Rieth et al. (2017), "Additional Tennessee Eastman Process Simulation Data for Anomaly Detection Evaluation", Harvard Dataverse DOI:10.7910/DVN/6C3JR1

## ساختار
- 52 متغیر فرآیندی (41 اندازه‌گیری XMEAS + 11 متغیر دستکاری XMV)
- 22 سناریو: خطای 0 (نرمال) تا خطای 21
- آموزش: 500 نمونه برای هر خطا
- آزمون: 960 نمونه برای هر خطا (160 نمونه نرمال + 800 نمونه خطا-دار)
- فایل‌های پردازش‌شده: data/real/processed/tep_train.csv, tep_test.csv

## مرتبط با پتروشیمی غدیر
TEP یک بنچ‌مارک استاندارد دانشگاهی برای تشخیص خطا و ایمنی فرآیند است. ساختار چند-متغیره و الگوهای خطای آن مشابه خطوط الفین/آروماتیک مجتمع غدیر است و برای ارزیابی
ماژول‌های دوم و سوم BHAM (پایش لایه‌های حفاظتی و پیش‌بینی توالی) به‌کار می‌رود.
