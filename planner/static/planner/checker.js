(function () {
    'use strict';

    var form = document.querySelector('[data-checker-form]');
    if (!form) {
        return;
    }

    form.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-category-info]');
        if (!btn) {
            return;
        }
        var desc = document.getElementById(btn.getAttribute('aria-controls'));
        if (!desc) {
            return;
        }
        var expanded = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', String(!expanded));
        desc.hidden = expanded;
    });

    var list = form.querySelector('[data-selected-list]');
    var emptyMsg = form.querySelector('[data-selected-empty]');
    var countEl = form.querySelector('[data-selected-count]');
    var totalEl = form.querySelector('[data-selected-total]');
    if (!list || !countEl || !totalEl) {
        return;
    }

    function formatCp(value) {
        // Trim trailing zeroes / decimal point for display parity with Django's
        // floatformat:'-2' filter used elsewhere on the page.
        return String(Math.round(value * 100) / 100).replace(/\.0+$/, '');
    }

    function rebuild() {
        var checked = form.querySelectorAll(
            'input[type="checkbox"][name="courses"]:checked'
        );
        list.innerHTML = '';
        var total = 0;
        checked.forEach(function (input) {
            var code = input.dataset.courseCode || '';
            var title = input.dataset.courseTitle || '';
            var cp = parseFloat(input.dataset.courseCp || '0');
            if (!isNaN(cp)) total += cp;

            var li = document.createElement('li');
            li.className = 'selected__item';

            var codeEl = document.createElement('span');
            codeEl.className = 'selected__item-code';
            codeEl.textContent = code;

            var titleEl = document.createElement('span');
            titleEl.className = 'selected__item-title';
            titleEl.textContent = title;

            var cpEl = document.createElement('span');
            cpEl.className = 'selected__item-cp';
            cpEl.textContent = formatCp(cp) + ' CP';

            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'selected__remove';
            remove.setAttribute('aria-label', 'Remove ' + code);
            remove.textContent = '\u00d7';
            remove.addEventListener('click', function () {
                input.checked = false;
                rebuild();
            });

            li.appendChild(codeEl);
            li.appendChild(titleEl);
            li.appendChild(cpEl);
            li.appendChild(remove);
            list.appendChild(li);
        });

        countEl.textContent = String(checked.length);
        totalEl.textContent = formatCp(total);
        if (emptyMsg) {
            emptyMsg.hidden = checked.length > 0;
        }
    }

    form.addEventListener('change', function (e) {
        if (e.target && e.target.matches('input[type="checkbox"][name="courses"]')) {
            rebuild();
        }
    });

    rebuild();
})();
