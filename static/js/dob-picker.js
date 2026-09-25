window.DobPicker = (function () {
    var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    function daysInMonth(year, monthIndex) {
        return new Date(year, monthIndex + 1, 0).getDate();
    }

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function attach(input, options) {
        options = options || {};
        var minAge = options.minAge || 12;
        var maxAge = options.maxAge || 28;
        var today = new Date();
        var maxYear = today.getFullYear() - minAge;
        var minYear = today.getFullYear() - maxAge;

        var state = { year: null, month: null, day: null };

        if (input.value) {
            var parts = input.value.split('-');
            if (parts.length === 3) {
                state.year = parseInt(parts[0], 10);
                state.month = parseInt(parts[1], 10) - 1;
                state.day = parseInt(parts[2], 10);
            }
        }

        input.readOnly = true;
        input.classList.add('dob-picker-input');
        if (!input.value) {
            input.placeholder = options.placeholder || 'Select your date of birth';
        }

        var wrap = document.createElement('div');
        wrap.className = 'dob-picker-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        var panel = document.createElement('div');
        panel.className = 'dob-picker-panel' + (options.theme === 'dark' ? ' dob-picker-panel--dark' : '');
        panel.innerHTML =
            '<div class="dob-picker-head">' +
                '<span>Date of birth</span>' +
                '<button type="button" class="dob-picker-close" aria-label="Close">&times;</button>' +
            '</div>' +
            '<p class="dob-picker-label">Year <span class="dob-picker-range">(' + minYear + '–' + maxYear + ')</span></p>' +
            '<div class="dob-picker-year-boxes"></div>' +
            '<p class="dob-picker-label">Month</p>' +
            '<div class="dob-picker-months"></div>' +
            '<p class="dob-picker-label">Day</p>' +
            '<div class="dob-picker-days"></div>' +
            '<button type="button" class="dob-picker-done" disabled>Done</button>';
        wrap.appendChild(panel);

        var yearBoxesWrap = panel.querySelector('.dob-picker-year-boxes');
        var yearDigits = [0, 0, 0, 0];
        var yearBoxes = [];
        for (var d = 0; d < 4; d += 1) {
            var box = document.createElement('input');
            box.type = 'text';
            box.inputMode = 'numeric';
            box.maxLength = 1;
            box.className = 'dob-picker-digit';
            (function (idx) {
                box.addEventListener('input', function () {
                    var val = box.value.replace(/[^0-9]/g, '').slice(-1);
                    box.value = val;
                    if (val && yearBoxes[idx + 1]) {
                        yearBoxes[idx + 1].focus();
                    }
                    syncYear();
                });
                box.addEventListener('keydown', function (e) {
                    if (e.key === 'Backspace' && !box.value && yearBoxes[idx - 1]) {
                        yearBoxes[idx - 1].focus();
                    }
                });
            })(d);
            yearBoxes.push(box);
            yearBoxesWrap.appendChild(box);
        }

        function syncYear() {
            var str = yearBoxes.map(function (b) { return b.value || ''; }).join('');
            if (str.length === 4) {
                var year = parseInt(str, 10);
                if (year >= minYear && year <= maxYear) {
                    state.year = year;
                } else {
                    state.year = null;
                }
            } else {
                state.year = null;
            }
            renderDays();
            updateDoneState();
        }

        if (state.year) {
            String(state.year).split('').forEach(function (ch, idx) {
                yearBoxes[idx].value = ch;
            });
        }

        var monthsWrap = panel.querySelector('.dob-picker-months');
        MONTHS.forEach(function (label, idx) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'dob-picker-chip';
            btn.textContent = label;
            btn.addEventListener('click', function () {
                state.month = idx;
                monthsWrap.querySelectorAll('.dob-picker-chip').forEach(function (el) {
                    el.classList.remove('is-active');
                });
                btn.classList.add('is-active');
                renderDays();
                updateDoneState();
            });
            monthsWrap.appendChild(btn);
        });

        var daysWrap = panel.querySelector('.dob-picker-days');

        function renderDays() {
            daysWrap.innerHTML = '';
            var year = state.year || today.getFullYear();
            var month = state.month !== null ? state.month : 0;
            var total = daysInMonth(year, month);
            if (state.day && state.day > total) {
                state.day = null;
            }
            for (var day = 1; day <= total; day += 1) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'dob-picker-chip dob-picker-chip--day';
                btn.textContent = pad(day);
                if (state.day === day) {
                    btn.classList.add('is-active');
                }
                (function (d) {
                    btn.addEventListener('click', function () {
                        state.day = d;
                        daysWrap.querySelectorAll('.dob-picker-chip').forEach(function (el) {
                            el.classList.remove('is-active');
                        });
                        btn.classList.add('is-active');
                        updateDoneState();
                    });
                })(day);
                daysWrap.appendChild(btn);
            }
        }

        var doneBtn = panel.querySelector('.dob-picker-done');

        function updateDoneState() {
            doneBtn.disabled = !(state.year && state.month !== null && state.day);
        }

        doneBtn.addEventListener('click', function () {
            var iso = state.year + '-' + pad(state.month + 1) + '-' + pad(state.day);
            input.value = iso;
            input.dispatchEvent(new Event('change', { bubbles: true }));
            var display = new Date(state.year, state.month, state.day);
            input.setAttribute('data-display', display.toDateString());
            renderDisplay();
            closePanel();
        });

        function renderDisplay() {
            if (state.year && state.month !== null && state.day) {
                var months = MONTHS[state.month];
                input.value = state.year + '-' + pad(state.month + 1) + '-' + pad(state.day);
                input.setAttribute('data-friendly', pad(state.day) + ' ' + months + ' ' + state.year);
                if (options.friendlyTarget) {
                    var target = document.querySelector(options.friendlyTarget);
                    if (target) {
                        target.textContent = pad(state.day) + ' ' + months + ' ' + state.year;
                    }
                }
            }
        }

        panel.querySelector('.dob-picker-close').addEventListener('click', closePanel);

        function openPanel() {
            panel.classList.add('is-open');
            if (state.month !== null) {
                var activeMonthBtn = monthsWrap.children[state.month];
                if (activeMonthBtn) activeMonthBtn.classList.add('is-active');
            }
            renderDays();
            updateDoneState();
        }

        function closePanel() {
            panel.classList.remove('is-open');
        }

        input.addEventListener('click', function () {
            if (panel.classList.contains('is-open')) {
                closePanel();
            } else {
                openPanel();
            }
        });

        document.addEventListener('click', function (e) {
            if (!wrap.contains(e.target)) {
                closePanel();
            }
        });

        if (state.year && state.month !== null && state.day) {
            renderDisplay();
        }

        return { close: closePanel };
    }

    return { attach: attach };
})();
