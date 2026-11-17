# گزارش بنچ‌مارک و تحلیل شکاف (Benchmark & Gap Analysis)

**محصول:** BHAM — Barrier Health & Alarm Manager
**نسخه:** 2.0.0 (بهینه‌شده پس از بنچ‌مارک)
**تاریخ:** ۱۴۰۵/۰۸/۱۷
**مجتمع:** پتروشیمی غدیر
**توسعه‌دهنده:** شرکت پتروپالاتوس

---

## ۱. هدف

این سند محصول BHAM را با استانداردهای بین‌المللی مدیریت آلارم و محصولات تجاری مرجع بنچ‌مارک می‌کند، شکاف‌های نسخه ۱.۰.۰ را شناسایی می‌نماید و بهینه‌سازی‌های اعمال‌شده در نسخه ۲.۰.۰ را مستند می‌سازد. این بنچ‌مارک مبنای ادعای انطباق محصول با EEMUA 191، ANSI/ISA-18.2، IEC 62682 و IEC 61511 است.

---

## ۲. استانداردهای مرجع

| استاندارد | عنوان | حوزه | وضعیت در BHAM v2 |
|---|---|---|---|
| **EEMUA 191** (v4, Nov 2024) | Alarm Systems — A Guide to Design, Management and Procurement | KPI‌ها، طوفان، چترینگ، stale، bad-actor | ✅ پیاده‌سازی کامل |
| **ANSI/ISA-18.2** (2016) | Management of Alarm Systems for the Process Industries | چرخه ۱۰ مرحله‌ای مدیریت آلارم | ✅ Rationalization + Shelving + Monitoring |
| **IEC 62682** | Management of alarm systems for the process industries (نسخه بین‌المللی ISA-18.2) | Shelving اجباری، تقویت «should→shall» | ✅ Shelving اجباری |
| **IEC 61511** | Functional safety — SIS for process industry | SIL، PFD، LOPA، IPL | ✅ تخمین SIL + LOPA |
| **IEC 61508** | Functional safety of E/E/PE systems | پایه SIL | ✅ (ارجاع) |
| **API RP 1160** | Managing SCADA alarms for pipelines | مدیریت آلارم SCADA | ⚠️ مرتبع (pipeline) |
| **OSHA PSM 1910.119** | Process Safety Management | الزامات آلارم ایمنی | ✅ (از طریق IEC 61511) |
| **NIST SP 800-82 r3** | OT security | امنیت پلتفرم آلارم | 📋 مرجع امنیتی |

---

## ۳. KPI‌های استاندارد EEMUA 191 / ISA-18.2 و وضعیت BHAM

جدول زیر اهداف استاندارد و وضعیت پیاده‌سازی در BHAM v2 را نشان می‌دهد. تمامی اهداف به‌صورت کد در `EEMUA_TARGETS` (ماژول `alarm_analytics.py`) تعریف شده‌اند و از طریق endpoint `/api/v1/alarms/kpi/eemua` قابل دسترسی هستند.

| شاخص | هدف EEMUA/ISA | حد مداخله | وضعیت BHAM v1 | وضعیت BHAM v2 |
|---|---|---|---|---|
| نرخ آلارم پایدار (per operator per 10 min) | ≤ ۱ | — | ❌ فقط per hour | ✅ per 10min + steady/peak |
| نرخ آلارم پس از اختلال (first 10 min) | ≤ ۱۰ | — | ❌ نبود | ✅ peak_rate |
| چترینگ (≥ ۳ آلارم در ۱ دقیقه) | ~۰ | ≤ ۱٪ تگ‌ها | ⚠️ تعریف ضعیف | ✅ هر دو معیار EEMUA (۱min/9min) |
| آلارم ثابت‌مانده (Standing, > 24h) | ~۰ | ≤ ۵ | ❌ نبود | ✅ standing_alarms + pct |
| آلارم stale (> 24h و قبلاً فعال) | ~۰ | ≤ ۱٪ | ❌ نبود | ✅ stale_alarms + pct |
| طوفان آلارم (> ۱۰ در ۱۰ دقیقه) | کاهش | — | ⚠️ فقط تعداد | ✅ flood_events + max_concurrent + total_alarms |
| سهم ۱۰ تگ برتر (Bad Actors) | ≤ ۱٪ | ≤ ۵٪ | ⚠️ محاسبه بدون هدف | ✅ top_10_share_pct + bad_actors + bad_actors_share_pct |
| توزیع اولویت (Low/Med/High/Crit) | ۸۰/۱۵/۴/۱ | — | ❌ نبود | ✅ priority_distribution + priority_compliance |
| نرخ تأیید (Ack ≤ ۳۰ ثانیه) | ≥ ۸۰٪ | — | ❌ نبود | ✅ ack_compliance_pct |
| آلارم/اپراتور/روز | ≤ ۱۴۴ | — | ❌ نبود | ✅ alarms_per_operator_per_day |
| نرخ اعلام (Annunciation per min) | پایش | — | ❌ نبود | ✅ annunciation_rate |
| امتیاز انطباق کلی | — | — | ❌ نبود | ✅ compliance_score (0-100) + grade (A-D) |

---

## ۴. چرخه ۱۰ مرحله‌ای ISA-18.2 و پوشش BHAM

| مرحله | نام | پوشش در BHAM v2 |
|---|---|---|
| A | Alarm Philosophy | 📋 مرجع (BRS) |
| B | Identification | ✅ تشخیص خودکار آلارم از لاگ DCS |
| C | **Rationalization** | ✅ متد `rationalize()` + endpoint `/alarms/rationalize` |
| D | Detailed Design | ✅ پیشنهاد آستانه (3σ) + deadband |
| E | Implementation | ✅ استقرار در FastAPI |
| F | Operation | ✅ داشبورد زنده |
| G | Maintenance | ✅ بهینه‌سازی فاصله تست (RBI) |
| H | **Monitoring & Assessment** | ✅ KPI کامل EEMUA + compliance score |
| I | Management of Change | 📋 مرجع |
| J | Audit | 📋 مرجع |

---

## ۵. بنچ‌مارک با محصولات تجاری بین‌المللی

جدول مقایسه BHAM v2 با محصولات پیشرو مدیریت آلارم (منبع: صفحات رسمی فروشندگان، Nov 2026):

| قابلیت | PAS PlantState Integrity | Honeywell Forge | ABB 800xA AlarmInsight | AspenTech InfoPlus.21 + Mtell | GE Proficy iFIX | Yokogawa Exaquantum | Siemens PCS 7 | **BHAM v2** |
|---|---|---|---|---|---|---|---|---|
| Rationalization DB | ✅ leader | Partial | Partial | Partial | NSP | Partial | Partial | ✅ خودکار |
| Bad-actor analytics | ✅ | ✅ | ✅ | ✅ | Partial | ✅ | Partial | ✅ |
| KPI dashboards (EEMUA) | ✅ | ✅ | ✅ | ✅ | Partial | ✅ | Partial | ✅ |
| State-based alarming | ✅ | ✅ | Partial | Partial | ✅ | ✅ | ✅ | ✅ |
| Dynamic suppression | ✅ | ✅ | Partial | Partial | ✅ | ✅ | ✅ | ✅ (shelving) |
| Shelving (IEC 62682) | ✅ | ✅ | ✅ | Partial | ✅ | ✅ | ✅ | ✅ |
| AI/ML predictive | Partial | Partial | Partial | ✅ (Mtell) | NSP | Partial | NSP | ✅ (Isolation Forest + RF + XGBoost) |
| IPL/LOPA (IEC 61511) | Partial | Partial | Partial | Partial | NSP | Partial | NSP | ✅ |
| SIL تخمین | NSP | Partial | Partial | Partial | NSP | Partial | NSP | ✅ |
| Compliance score (EEMUA) | Partial | Partial | Partial | Partial | NSP | Partial | NSP | ✅ |
| Multi-horizon forecasting | NSP | NSP | NSP | ✅ (Mtell) | NSP | NSP | NSP | ✅ (1h/24h/72h) |
| Open API (REST) | NSP | NSP | NSP | NSP | NSP | NSP | NSP | ✅ FastAPI |
| RTL/فارسی | NSP | NSP | NSP | NSP | NSP | NSP | NSP | ✅ |

**NSP** = Not Stated Publicly؛ **Partial** = پشتیبانی جزئی.

### یافته‌های کلیدی بنچ‌مارک

۱. **هسته تخصصی:** PAS PlantState Integrity و Honeywell Forge در rationalization پیشتازند؛ DCS-native modules (Yokogawa AAASuite, Siemens, Rockwell, GE) در runtime suppression/shelving قوی‌اند.

۲. **AI/ML:** تنها Aspen Mtell لایه AI تولیدی مستند دارد، اما آن را از لایه آلارم جدا نگه می‌دارد. BHAM v2 یکپارچگی AI را در خود لایه آلارم فراهم می‌کند.

۳. **هیچ فروشنده‌ای** به‌صورت عمومی production-grade AI-based root-cause analysis برای operator alarms مستند ندارد — این یک شکاف نوظهور است که BHAM آن را هدف قرار می‌دهد.

۴. **LOPA + SIL به‌صورت یکپارچه با آلارم** در هیچ‌یک از محصولات دیده نشد — معمولاً در ابزارهای جداگانه functional safety نگهداری می‌شود. BHAM v2 این دو را در یک پلتفرم ادغام می‌کند.

---

## ۶. شکاف‌های نسخه ۱.۰.۰ و بهینه‌سازی‌های نسخه ۲.۰.۰

### ۶.۱ شکاف‌های شناسایی‌شده در v1

| شکاف | اولویت | توضیح |
|---|---|---|
| عدم محاسبه alarms per 10min | بالا | EEMUA شاخص ساعت ندارد، شاخص ۱۰ دقیقه دارد |
| عدم تشخیص چترینگ با معیار دوگانه | بالا | EEMUA: ≥ ۳ در ۱ دقیقه یا ≥ ۹ در ۹ دقیقه |
| نبود شاخص standing/stale | بالا | آلارم‌های Active > 24h |
| نبود توزیع اولویت و compliance | بالا | هدف ۸۰/۱۵/۴/۱ |
| نبود bad-actor analytics | بالا | تگ‌هایی که > ۵٪ آلارم تولید می‌کنند |
| نبود Rationalization خودکار | بالا | مرحله ISA-18.2 |
| نبود Shelving (الزام IEC 62682) | بالا | خاموش موقت آلارم |
| نبود State-based suppression | متوسط | خاموش خودکار بر اساس حالت فرآیند |
| نبود SIL/PFD محقق‌شده | بالا | IEC 61511 |
| نبود LOPA | بالا | کفایت لایه‌های حفاظتی |
| نبود مدیریت زمان بایپس | متوسط | حد SIL |
| نبود horizon چندمرحله‌ای در پیش‌بینی | متوسط | 1h/24h/72h |
| نبود امتیاز انطباق کلی | بالا | grade A-D |
| نبود endpoint‌های API استاندارد | بالا | KPI/rationalize/shelve/lopa |

### ۶.۲ بهینه‌سازی‌های اعمال‌شده در v2

**ماژول آلارم (`alarm_analytics.py`):**
- ✅ افزودن ۱۵ فیلد جدید به `AlarmMetrics` شامل تمام KPI‌های EEMUA
- ✅ تشخیص چترینگ با هر دو معیار EEMUA (1min/9min)
- ✅ تشخیص طوفان با شروع/پایان و حداکثر همزمانی
- ✅ تشخیص standing/stale با استفاده از `duration_h` و `prev_active_count`
- ✅ توزیع اولویت + امتیاز انطباق با هدف ۸۰/۱۵/۴/۱
- ✅ bad-actor identification (تگ‌های > ۵٪)
- ✅ متریک‌های اپراتور (alarms_per_operator_per_day, ack_compliance)
- ✅ متد `rationalize()` با ۴ اقدام (Keep/Reprioritize/Retune/Remove)
- ✅ متد `shelve()` / `unshelve()` / `filter_shelved()` (IEC 62682)
- ✅ متد `state_based_suppression()` با ۳ حالت فرآیند
- ✅ متد `compliance_report()` با شکاف‌شناسی خودکار
- ✅ امتیاز compliance 0-100 و گرید A-D

**ماژول لایه‌های حفاظتی (`barrier_health.py`):**
- ✅ تخمین PFD با مدل Poisson بهبودیافته
- ✅ تعیین SIL محقق‌شده (1-4) بر اساس PFD مطابق IEC 61511 Table 3
- ✅ تعیین SIL هدف بر اساس نوع لایه (BPCS=1, SIS=2, ESD=3, ...)
- ✅ شناسایی شکاف SIL (OK / Below-target)
- ✅ متد `lopa_analysis()` با محاسبه RRF کل و مقایسه با RRF لازم
- ✅ مدیریت زمان بایپس با حداکثر مجاز بر اساس SIL (`MAX_BYPASS_H_PER_YEAR`)
- ✅ فواصل تست بر اساس SIL هدف (`SIL_TEST_INTERVAL_MONTHS`)
- ✅ متد `bypass_events()` با تشخیص تخلف از حد SIL

**ماژول پیش‌بینی توالی (`sequence_prediction.py`):**
- ✅ افزودن horizon ۱ ساعت (prob_shutdown_1h)
- ✅ افزودن horizon ۲۴ ساعت (prob_shutdown_24h)
- ✅ افزودن horizon ۷۲ ساعت (prob_shutdown_72h)
- ✅ تخمین lead_time_to_shutdown_min
- ✅ فیلد confidence (اعتماد پیش‌بینی)
- ✅ فیلد recommended_intervention (اقدام پیشنهادی بر اساس horizon)

**API (`api/server.py`):**
- ✅ endpoint `POST /api/v1/alarms/kpi/eemua`
- ✅ endpoint `POST /api/v1/alarms/rationalize`
- ✅ endpoint `POST /api/v1/alarms/shelve`
- ✅ endpoint `POST /api/v1/alarms/shelve/batch`
- ✅ endpoint `DELETE /api/v1/alarms/shelve/{tag}`
- ✅ endpoint `GET /api/v1/alarms/shelved`
- ✅ endpoint `POST /api/v1/alarms/state-based-suppression`
- ✅ endpoint `POST /api/v1/barriers/lopa`
- ✅ endpoint `POST /api/v1/barriers/bypass-events`
- ✅ به‌روزرسانی `analyze_alarms` با compliance report

**Dashboard (`frontend/dashboard.html`):**
- ✅ پنل امتیاز انطباق و گرید (A-D)
- ✅ جدول کامل EEMUA با مقایسه مقدار/هدف/وضعیت
- ✅ نمودار توزیع اولویت با هدف ۸۰/۱۵/۴/۱
- ✅ پنل نرخ پایدار/اوج
- ✅ پنل bad-actors
- ✅ پنل Rationalization با خلاصه اقدامات
- ✅ پنل KPI لایه‌های حفاظتی (SIL مطابق/زیر هدف/بایپس/تخلف)
- ✅ جدول لایه‌ها با ستون SIL محقق/هدف/وضعیت
- ✅ پنل LOPA با RRF و کفایت
- ✅ پنل horizon چندمرحله‌ای (1h/24h/72h) برای پیش‌بینی توالی

**تست‌ها:**
- ✅ افزودن ۲۹ تست جدید در `tests/test_benchmark_features.py`
- ✅ پوشش ۹۴٪ حفظ شد (مجموع ۷۸ تست)

---

## ۷. شاخص‌های کمی بهبود

| شاخص | v1 | v2 | بهبود |
|---|---|---|---|
| تعداد KPI‌های EEMUA/ISA | ۷ | ۲۰ | +۱۸۶٪ |
| تعداد endpointهای API | ۶ | ۱۵ | +۱۵۰٪ |
| تعداد تست‌ها | ۴۹ | ۷۸ | +۵۹٪ |
| پوشش کد | ۹۴٪ | ۹۴٪ | ثابت |
| مطابقت با IEC 62682 (Shelving) | ❌ | ✅ | جدید |
| مطابقت با IEC 61511 (SIL/LOPA) | ❌ | ✅ | جدید |
| مطابقت با ISA-18.2 (Rationalization) | ❌ | ✅ | جدید |
| امتیاز انطباق خودکار | ❌ | ✅ | جدید |

---

## ۸. توصیه‌های فاز بعدی (TRL 6+)

۱. **ادغام با DCS واقعی:** اتصال به OPC-UA / OPC-DA برای دریافت زنده آلارم‌ها.
۲. **ML پیشرفته root-cause:** تعبیه graph neural network برای کشف علت ریشه‌ای در شبکه تگ.
۳. **Alarm Philosophy Document:** تولید خودکار سند فلسفه آلارم مطابق ISA-18.2 مرحله A.
۴. **مدیریت تغییر (MOC):** ثبت تغییرات پیکربندی آلارم با workflow تأیید.
۵. **Pilot deployment:** استقرار روی یک واحد از مجتمع غدیر برای TRL 6.
۶. **ابزار audit:** گزارش دورانی مطابقت با EEMUA برای ممیزی سالانه.

---

## ۹. منابع و مراجع

- EEMUA 191 v4 (Nov 2024): https://www.eemua.org/Products/Publications/EEMUA-191.aspx
- ANSI/ISA-18.2-2016: https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa18
- IEC 62682: https://webstore.iec.ch/publication/7549
- IEC 61511: https://webstore.iec.ch/publication/5534
- API RP 1160: https://www.api.org/products-and-services/standards
- OSHA PSM 1910.119: https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.119
- NIST SP 800-82 r3: https://csrc.nist.gov/pubs/sp/800/82/r3/final
- PAS PlantState Integrity (Hexagon): https://hexagon.com/products/production-software/plant-state-integrity
- Honeywell Forge: https://www.honeywellprocess.com/en-US/explore/products/advanced-applications/honeywell-forge
- ABB 800xA Alarm Management: https://new.abb.com/control-systems/system-800xa/features/alarm-management
- AspenTech InfoPlus.21: https://www.aspentech.com/en/products/msi/aspen-infoplus21
- GE Vernova Proficy: https://www.ge.com/digital/applications/operations-performance
- Yokogawa Exaquantum: https://www.yokogawa.com/solutions/products-and-services/control-systems/

---

## ۱۰. جمع‌بندی

بنچ‌مارک نشان می‌دهد BHAM v2 در هسته قابلیت‌های مدیریت آلارم با محصولات تجاری پیشرو برابری می‌کند و در سه محور متمایز است:
۱. **ادغام یکپارچه آلارم + functional safety** (SIL/LOPA در همان پلتفرم)
۲. **لایه AI در خود آلارم** (نه جداگانه مثل Mtell)
۳. **امتیاز انطباق خودکار با استانداردهای بین‌المللی** + داشبورد فارسی RTL + REST API باز

این بهینه‌سازی‌ها مبنای ارتقا از TRL 5 به مسیر TRL 6 (نمونه سیستم در محیط مرتبط) را فراهم می‌سازند و محصول را برای پایلوت در مجتمع پتروشیمی غدیر آماده می‌کنند.
