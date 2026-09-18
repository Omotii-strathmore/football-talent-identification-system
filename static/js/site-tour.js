window.SiteTour = (function () {
    function create(steps, options) {
        options = options || {};
        var storageKey = options.storageKey || 'siteTourDone';
        var btnPosKey = storageKey + 'BtnPos';
        var autoStart = options.autoStart !== false;
        var autoStartDelay = options.autoStartDelay || 700;

        var dim = document.createElement('div');
        dim.className = 'st-dim';

        var highlight = document.createElement('div');
        highlight.className = 'st-highlight';

        var tooltip = document.createElement('div');
        tooltip.className = 'st-tooltip';
        tooltip.setAttribute('role', 'dialog');
        tooltip.innerHTML =
            '<p class="st-step-label"></p>' +
            '<h4 class="st-title"></h4>' +
            '<p class="st-desc"></p>' +
            '<div class="st-dots"></div>' +
            '<div class="st-actions">' +
            '<button type="button" class="st-skip">Skip tutorial</button>' +
            '<div class="st-nav-btns">' +
            '<button type="button" class="st-back">Back</button>' +
            '<button type="button" class="st-next">Next</button>' +
            '</div>' +
            '</div>';

        var replayBtn = document.createElement('button');
        replayBtn.type = 'button';
        replayBtn.className = 'st-replay-btn';
        replayBtn.setAttribute('aria-label', 'Take the tour');
        replayBtn.setAttribute('title', 'Take the tour');
        replayBtn.textContent = '🎬';

        var welcome = options.welcome || null;
        var welcomeKey = storageKey + 'WelcomeSeen';
        var welcomeModal = null;
        if (welcome) {
            welcomeModal = document.createElement('div');
            welcomeModal.className = 'st-tooltip st-welcome';
            welcomeModal.innerHTML =
                '<h4 class="st-title"></h4>' +
                '<p class="st-desc"></p>' +
                '<div class="st-actions" style="justify-content:flex-end;">' +
                '<button type="button" class="st-next st-welcome-continue">Let\'s go</button>' +
                '</div>';
            welcomeModal.querySelector('.st-title').textContent = '🥳 ' + (welcome.title || '');
            welcomeModal.querySelector('.st-desc').textContent = welcome.message || '';
        }

        function spawnConfetti() {
            var colors = ['#f59e0b', '#ef4444', '#10b981', '#3b82f6', '#a855f7', '#ec4899'];
            var container = document.createElement('div');
            container.className = 'st-confetti';
            for (var i = 0; i < 46; i += 1) {
                var piece = document.createElement('div');
                piece.className = 'st-confetti-piece';
                var left = Math.random() * 100;
                var color = colors[Math.floor(Math.random() * colors.length)];
                var duration = 2.2 + Math.random() * 1.6;
                var delay = Math.random() * 0.5;
                var rotateStart = Math.random() * 360;
                var drift = (Math.random() * 60 - 30) + 'px';
                piece.style.left = left + 'vw';
                piece.style.background = color;
                piece.style.animationDuration = duration + 's';
                piece.style.animationDelay = delay + 's';
                piece.style.setProperty('--st-confetti-drift', drift);
                piece.style.transform = 'rotate(' + rotateStart + 'deg)';
                container.appendChild(piece);
            }
            document.body.appendChild(container);
            setTimeout(function () {
                container.remove();
            }, 4200);
        }

        document.body.appendChild(dim);
        document.body.appendChild(highlight);
        document.body.appendChild(tooltip);
        if (welcomeModal) {
            document.body.appendChild(welcomeModal);
        }
        document.body.appendChild(replayBtn);

        var stepLabel = tooltip.querySelector('.st-step-label');
        var titleEl = tooltip.querySelector('.st-title');
        var descEl = tooltip.querySelector('.st-desc');
        var dotsWrap = tooltip.querySelector('.st-dots');
        var backBtn = tooltip.querySelector('.st-back');
        var nextBtn = tooltip.querySelector('.st-next');
        var skipBtn = tooltip.querySelector('.st-skip');

        var currentStep = 0;
        var active = false;

        steps.forEach(function (_, idx) {
            var dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'st-dot';
            dot.setAttribute('aria-label', 'Go to step ' + (idx + 1));
            dot.addEventListener('click', function () {
                currentStep = idx;
                renderStep();
            });
            dotsWrap.appendChild(dot);
        });

        function positionForTarget(target) {
            if (!target) {
                highlight.classList.remove('is-active');
                var tw = tooltip.offsetWidth || 320;
                var th = tooltip.offsetHeight || 200;
                tooltip.style.top = Math.max(16, (window.innerHeight - th) / 2) + 'px';
                tooltip.style.left = Math.max(16, (window.innerWidth - tw) / 2) + 'px';
                return;
            }

            var el = document.querySelector(target);
            if (!el) {
                positionForTarget(null);
                return;
            }

            el.scrollIntoView({ behavior: 'smooth', block: 'center' });

            setTimeout(function () {
                var rect = el.getBoundingClientRect();
                var pad = 8;

                highlight.classList.add('is-active');
                highlight.style.top = (rect.top - pad) + 'px';
                highlight.style.left = (rect.left - pad) + 'px';
                highlight.style.width = (rect.width + pad * 2) + 'px';
                highlight.style.height = (rect.height + pad * 2) + 'px';

                var tw = tooltip.offsetWidth || 320;
                var th = tooltip.offsetHeight || 200;
                var top = rect.bottom + pad + 14;
                if (top + th > window.innerHeight - 16) {
                    top = Math.max(16, rect.top - pad - 14 - th);
                }
                var left = Math.min(Math.max(16, rect.left), window.innerWidth - tw - 16);

                tooltip.style.top = top + 'px';
                tooltip.style.left = left + 'px';
            }, 320);
        }

        function renderStep() {
            var step = steps[currentStep];
            stepLabel.textContent = 'Step ' + (currentStep + 1) + ' of ' + steps.length;
            titleEl.textContent = step.title;
            descEl.textContent = step.desc;
            backBtn.disabled = currentStep === 0;
            nextBtn.textContent = currentStep === steps.length - 1 ? 'Got it' : 'Next';

            var dots = dotsWrap.querySelectorAll('.st-dot');
            for (var i = 0; i < dots.length; i += 1) {
                dots[i].classList.toggle('is-active', i === currentStep);
            }

            positionForTarget(step.target);
        }

        function startTour() {
            active = true;
            currentStep = 0;
            dim.classList.add('is-active');
            tooltip.classList.add('is-active');
            renderStep();
        }

        function endTour() {
            active = false;
            dim.classList.remove('is-active');
            tooltip.classList.remove('is-active');
            highlight.classList.remove('is-active');
            try { localStorage.setItem(storageKey, '1'); } catch (e) {}
        }

        nextBtn.addEventListener('click', function () {
            if (currentStep === steps.length - 1) {
                endTour();
                return;
            }
            currentStep += 1;
            renderStep();
        });

        backBtn.addEventListener('click', function () {
            if (currentStep === 0) {
                return;
            }
            currentStep -= 1;
            renderStep();
        });

        skipBtn.addEventListener('click', endTour);

        var dragged = false;
        var dragStart = null;

        (function restoreButtonPosition() {
            var pos = null;
            try { pos = JSON.parse(localStorage.getItem(btnPosKey)); } catch (e) {}
            if (pos && typeof pos.left === 'number' && typeof pos.top === 'number') {
                var size = 42;
                var left = Math.min(Math.max(4, pos.left), window.innerWidth - size - 4);
                var top = Math.min(Math.max(4, pos.top), window.innerHeight - size - 4);
                replayBtn.style.left = left + 'px';
                replayBtn.style.top = top + 'px';
                replayBtn.style.right = 'auto';
                replayBtn.style.bottom = 'auto';
            }
        })();

        replayBtn.addEventListener('pointerdown', function (e) {
            dragged = false;
            var rect = replayBtn.getBoundingClientRect();
            dragStart = { x: e.clientX, y: e.clientY, left: rect.left, top: rect.top };
            replayBtn.setPointerCapture(e.pointerId);
            replayBtn.classList.add('is-dragging');
        });

        replayBtn.addEventListener('pointermove', function (e) {
            if (!dragStart) {
                return;
            }
            var dx = e.clientX - dragStart.x;
            var dy = e.clientY - dragStart.y;
            if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
                dragged = true;
            }
            if (dragged) {
                var size = replayBtn.offsetWidth;
                var newLeft = Math.min(Math.max(4, dragStart.left + dx), window.innerWidth - size - 4);
                var newTop = Math.min(Math.max(4, dragStart.top + dy), window.innerHeight - size - 4);
                replayBtn.style.left = newLeft + 'px';
                replayBtn.style.top = newTop + 'px';
                replayBtn.style.right = 'auto';
                replayBtn.style.bottom = 'auto';
            }
        });

        replayBtn.addEventListener('pointerup', function () {
            replayBtn.classList.remove('is-dragging');
            if (dragged) {
                var rect = replayBtn.getBoundingClientRect();
                try { localStorage.setItem(btnPosKey, JSON.stringify({ left: rect.left, top: rect.top })); } catch (e) {}
            } else {
                startTour();
            }
            dragStart = null;
        });

        window.addEventListener('resize', function () {
            if (active) {
                positionForTarget(steps[currentStep].target);
            }
        });

        function maybeAutoStartTour() {
            var seen = false;
            try { seen = !!localStorage.getItem(storageKey); } catch (e) {}
            if (autoStart && !seen) {
                setTimeout(startTour, autoStartDelay);
            } else {
                dim.classList.remove('is-active');
            }
        }

        if (welcomeModal) {
            welcomeModal.querySelector('.st-welcome-continue').addEventListener('click', function () {
                welcomeModal.classList.remove('is-active');
                try { localStorage.setItem(welcomeKey, '1'); } catch (e) {}
                maybeAutoStartTour();
            });

            var seenWelcome = false;
            try { seenWelcome = !!localStorage.getItem(welcomeKey); } catch (e) {}
            if (!seenWelcome) {
                setTimeout(function () {
                    dim.classList.add('is-active');
                    welcomeModal.classList.add('is-active');
                    spawnConfetti();
                }, 500);
            } else {
                maybeAutoStartTour();
            }
        } else {
            maybeAutoStartTour();
        }

        return { start: startTour, end: endTour };
    }

    return { create: create };
})();
