/*
 * Step-by-step date-of-birth picker: the player picks a year from a scrolling list,
 * then the months slide in, then the days. Dates outside the allowed age range are disabled.
 * Usage: DobPicker.attach(inputElement, { minAge: 12, maxAge: 28, theme: 'dark' | 'light' })
 */
window.DobPicker = (function () {
    var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
                  'August', 'September', 'October', 'November', 'December'];

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function daysInMonth(year, monthIndex) {
        return new Date(year, monthIndex + 1, 0).getDate();
    }

    function ageOn(year, monthIndex, day, today) {
        var age = today.getFullYear() - year;
        if (today.getMonth() < monthIndex || (today.getMonth() === monthIndex && today.getDate() < day)) {
            age -= 1;
        }
        return age;
    }

    function attach(input, options) {
        options = options || {};
        var minAge = options.minAge || 12;
        var maxAge = options.maxAge || 28;
        var today = new Date();
        var newestYear = today.getFullYear() - minAge;
        var oldestYear = today.getFullYear() - maxAge - 1;

        function isAllowed(year, month, day) {
            var age = ageOn(year, month, day, today);
            return age >= minAge && age <= maxAge;
        }

        function monthHasAllowedDay(year, month) {
            for (var d = 1; d <= daysInMonth(year, month); d += 1) {
                if (isAllowed(year, month, d)) return true;
            }
            return false;
        }

        var state = { year: null, month: null, day: null };
        if (input.value) {
            var parts = input.value.split('-').map(Number);
            if (parts.length === 3 && parts[0]) {
                state = { year: parts[0], month: parts[1] - 1, day: parts[2] };
            }
        }

        input.readOnly = true;
        input.classList.add('dob-picker-input');
        input.setAttribute('autocomplete', 'off');
        if (!input.value) {
            input.placeholder = options.placeholder || 'Tap to choose your date of birth';
        }

        var wrap = document.createElement('div');
        wrap.className = 'dob-picker-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        var panel = document.createElement('div');
        panel.className = 'dob-picker-panel' + (options.theme === 'dark' ? ' dob-picker-panel--dark' : '');
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'Choose your date of birth');
        panel.innerHTML =
            '<div class="dob-picker-head">' +
                '<div class="dob-picker-steps">' +
                    '<button type="button" class="dob-picker-step" data-step="year">Year</button>' +
                    '<span aria-hidden="true">&rsaquo;</span>' +
                    '<button type="button" class="dob-picker-step" data-step="month">Month</button>' +
                    '<span aria-hidden="true">&rsaquo;</span>' +
                    '<button type="button" class="dob-picker-step" data-step="day">Day</button>' +
                '</div>' +
                '<button type="button" class="dob-picker-close" aria-label="Close">&times;</button>' +
            '</div>' +
            '<div class="dob-picker-body">' +
                '<section class="dob-picker-section is-shown" data-section="year">' +
                    '<p class="dob-picker-label">1. Which year were you born?</p>' +
                    '<button type="button" class="dob-picker-chosen" data-open="year"></button>' +
                    '<div class="dob-picker-years" role="listbox" aria-label="Year"></div>' +
                '</section>' +
                '<section class="dob-picker-section" data-section="month">' +
                    '<p class="dob-picker-label">2. Which month?</p>' +
                    '<button type="button" class="dob-picker-chosen" data-open="month"></button>' +
                    '<div class="dob-picker-months"></div>' +
                '</section>' +
                '<section class="dob-picker-section" data-section="day">' +
                    '<p class="dob-picker-label">3. Which day?</p>' +
                    '<div class="dob-picker-days"></div>' +
                '</section>' +
            '</div>' +
            '<div class="dob-picker-foot">' +
                '<span class="dob-picker-summary">Start with your year of birth</span>' +
                '<button type="button" class="dob-picker-done" disabled>Done</button>' +
            '</div>';
        wrap.appendChild(panel);

        var body = panel.querySelector('.dob-picker-body');
        var yearsWrap = panel.querySelector('.dob-picker-years');
        var monthsWrap = panel.querySelector('.dob-picker-months');
        var daysWrap = panel.querySelector('.dob-picker-days');
        var summary = panel.querySelector('.dob-picker-summary');
        var doneBtn = panel.querySelector('.dob-picker-done');

        function section(name) {
            return panel.querySelector('[data-section="' + name + '"]');
        }

        function scrollToSection(name) {
            var target = section(name);
            // Scroll inside the panel only, so the page itself does not jump.
            body.scrollTo({ top: target.offsetTop - body.offsetTop, behavior: 'smooth' });
        }

        function reveal(name) {
            var target = section(name);
            if (!target.classList.contains('is-shown')) {
                target.classList.add('is-shown');
            }
            requestAnimationFrame(function () { scrollToSection(name); });
        }

        function hide(name) {
            section(name).classList.remove('is-shown');
        }

        // Once a step is answered it folds into one line ("Born in 2010 - change"), keeping the next step in view.
        function collapse(name, text) {
            var target = section(name);
            target.classList.add('is-collapsed');
            target.querySelector('.dob-picker-chosen').innerHTML =
                '<strong>' + text + '</strong><span>Change</span>';
        }

        function expand(name) {
            var target = section(name);
            if (!target.classList.contains('is-shown')) return;
            target.classList.remove('is-collapsed');
            if (name === 'year') centreYear();
            requestAnimationFrame(function () { scrollToSection(name); });
        }

        panel.querySelectorAll('.dob-picker-chosen').forEach(function (btn) {
            btn.addEventListener('click', function () { expand(btn.getAttribute('data-open')); });
        });

        function updateSteps() {
            var current = state.year === null ? 'year' : state.month === null ? 'month' : 'day';
            panel.querySelectorAll('.dob-picker-step').forEach(function (btn) {
                var step = btn.getAttribute('data-step');
                var done = (step === 'year' && state.year !== null) ||
                           (step === 'month' && state.month !== null) ||
                           (step === 'day' && state.day !== null);
                btn.classList.toggle('is-done', done);
                btn.classList.toggle('is-current', step === current && !done);
                btn.disabled = (step === 'month' && state.year === null) || (step === 'day' && state.month === null);
            });
        }

        function updateSummary() {
            if (state.year !== null && state.month !== null && state.day !== null) {
                var age = ageOn(state.year, state.month, state.day, today);
                summary.textContent = state.day + ' ' + MONTHS[state.month] + ' ' + state.year + ' (age ' + age + ')';
                doneBtn.disabled = false;
            } else if (state.year !== null && state.month !== null) {
                summary.textContent = MONTHS[state.month] + ' ' + state.year + ': now pick the day';
                doneBtn.disabled = true;
            } else if (state.year !== null) {
                summary.textContent = state.year + ': now pick the month';
                doneBtn.disabled = true;
            } else {
                summary.textContent = 'Start with your year of birth';
                doneBtn.disabled = true;
            }
            updateSteps();
        }

        // ---- Years: a scrolling list, newest first
        for (var y = newestYear; y >= oldestYear; y -= 1) {
            (function (year) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'dob-picker-year';
                btn.setAttribute('role', 'option');
                btn.setAttribute('data-year', year);
                btn.innerHTML = '<span>' + year + '</span><small>turning ' + (today.getFullYear() - year) + ' this year</small>';
                btn.addEventListener('click', function () { chooseYear(year); });
                yearsWrap.appendChild(btn);
            })(y);
        }

        // Put the chosen (or a typical) year in the middle of the scrolling list.
        function centreYear() {
            var focusYear = state.year !== null ? state.year : today.getFullYear() - 18;
            var yearBtn = yearsWrap.querySelector('[data-year="' + focusYear + '"]');
            if (yearBtn) {
                yearsWrap.scrollTop = yearBtn.offsetTop - yearsWrap.offsetTop - yearsWrap.clientHeight / 2 + yearBtn.clientHeight / 2;
            }
        }

        function markActive(container, selector, predicate) {
            container.querySelectorAll(selector).forEach(function (el) {
                var on = predicate(el);
                el.classList.toggle('is-active', on);
                if (el.hasAttribute('role')) el.setAttribute('aria-selected', on ? 'true' : 'false');
            });
        }

        function chooseYear(year) {
            state.year = year;
            markActive(yearsWrap, '.dob-picker-year', function (el) { return Number(el.getAttribute('data-year')) === year; });
            if (state.month !== null && !monthHasAllowedDay(year, state.month)) {
                state.month = null;
            }
            if (state.month !== null && state.day !== null &&
                (state.day > daysInMonth(year, state.month) || !isAllowed(year, state.month, state.day))) {
                state.day = null;
            }
            renderMonths();
            renderDays();
            collapse('year', 'Born in ' + year);
            if (state.month === null) {
                hide('day');
                section('month').classList.remove('is-collapsed');
            }
            reveal('month');
            updateSummary();
        }

        function renderMonths() {
            monthsWrap.innerHTML = '';
            MONTHS.forEach(function (label, idx) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'dob-picker-chip';
                btn.textContent = label.slice(0, 3);
                btn.title = label;
                btn.disabled = state.year === null || !monthHasAllowedDay(state.year, idx);
                btn.classList.toggle('is-active', state.month === idx);
                btn.addEventListener('click', function () { chooseMonth(idx); });
                monthsWrap.appendChild(btn);
            });
        }

        function chooseMonth(idx) {
            state.month = idx;
            if (state.day !== null && (state.day > daysInMonth(state.year, idx) || !isAllowed(state.year, idx, state.day))) {
                state.day = null;
            }
            renderMonths();
            renderDays();
            collapse('month', MONTHS[idx]);
            reveal('day');
            updateSummary();
        }

        function renderDays() {
            daysWrap.innerHTML = '';
            if (state.year === null || state.month === null) return;
            var total = daysInMonth(state.year, state.month);
            for (var d = 1; d <= total; d += 1) {
                (function (day) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'dob-picker-chip dob-picker-chip--day';
                    btn.textContent = day;
                    btn.disabled = !isAllowed(state.year, state.month, day);
                    btn.classList.toggle('is-active', state.day === day);
                    btn.addEventListener('click', function () {
                        state.day = day;
                        markActive(daysWrap, '.dob-picker-chip', function (el) { return Number(el.textContent) === day; });
                        updateSummary();
                        doneBtn.focus({ preventScroll: true });
                    });
                    daysWrap.appendChild(btn);
                })(d);
            }
        }

        panel.querySelectorAll('.dob-picker-step').forEach(function (btn) {
            btn.addEventListener('click', function () {
                expand(btn.getAttribute('data-step'));
            });
        });

        function commit() {
            input.value = state.year + '-' + pad(state.month + 1) + '-' + pad(state.day);
            input.setAttribute('data-friendly', state.day + ' ' + MONTHS[state.month] + ' ' + state.year);
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }

        doneBtn.addEventListener('click', function () {
            commit();
            closePanel();
        });

        panel.querySelector('.dob-picker-close').addEventListener('click', closePanel);

        function openPanel() {
            panel.classList.add('is-open');
            renderMonths();
            renderDays();
            if (state.year !== null) {
                section('month').classList.add('is-shown');
                collapse('year', 'Born in ' + state.year);
                markActive(yearsWrap, '.dob-picker-year', function (el) { return Number(el.getAttribute('data-year')) === state.year; });
                if (state.month !== null) {
                    section('day').classList.add('is-shown');
                    collapse('month', MONTHS[state.month]);
                }
            }
            updateSummary();
            centreYear();
            body.scrollTop = 0;
        }

        function closePanel() {
            panel.classList.remove('is-open');
        }

        input.addEventListener('click', function () {
            if (panel.classList.contains('is-open')) closePanel(); else openPanel();
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                openPanel();
            }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closePanel();
        });
        document.addEventListener('click', function (e) {
            // Buttons re-rendered during this click are detached; they were inside the picker, so ignore them.
            if (document.contains(e.target) && !wrap.contains(e.target)) closePanel();
        });

        return { close: closePanel, open: openPanel };
    }

    return { attach: attach };
})();
