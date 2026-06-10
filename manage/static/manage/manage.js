(function () {
    'use strict';

    var focusTrapHandler = null;

    function getModal() {
        return document.getElementById('modal');
    }

    function modalIsOpen() {
        var modal = getModal();
        return modal && modal.innerHTML.trim() !== '';
    }

    function getFocusableElements(container) {
        if (!container) {
            return [];
        }
        var selector = (
            'button:not([disabled]), [href], input:not([disabled]):not([type=hidden]), '
            + 'select:not([disabled]), textarea:not([disabled]), '
            + '[tabindex]:not([tabindex="-1"])'
        );
        return Array.prototype.slice.call(
            container.querySelectorAll(selector)
        ).filter(function (el) {
            if (el.closest('template')) {
                return false;
            }
            return el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement;
        });
    }

    function teardownFocusTrap() {
        if (focusTrapHandler) {
            document.removeEventListener('keydown', focusTrapHandler, true);
            focusTrapHandler = null;
        }
    }

    function setupFocusTrap() {
        teardownFocusTrap();
        var modal = getModal();
        if (!modal || !modalIsOpen()) {
            return;
        }
        focusTrapHandler = function (e) {
            if (e.key !== 'Tab' || !modalIsOpen()) {
                return;
            }
            var trapModal = getModal();
            if (!trapModal || !trapModal.contains(e.target)) {
                return;
            }
            var focusables = getFocusableElements(trapModal);
            if (focusables.length === 0) {
                return;
            }
            var first = focusables[0];
            var last = focusables[focusables.length - 1];
            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else if (document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        };
        document.addEventListener('keydown', focusTrapHandler, true);
    }

    function focusFirstInModal() {
        var modal = getModal();
        if (!modal) {
            return;
        }
        var firstField = modal.querySelector(
            'input:not([type=hidden]):not([type=checkbox]), select, textarea'
        );
        if (firstField && !firstField.closest('template')) {
            firstField.focus();
            return;
        }
        var focusables = getFocusableElements(modal);
        if (focusables.length) {
            focusables[0].focus();
        }
    }

    function closeModal() {
        teardownFocusTrap();
        var modal = getModal();
        if (modal) {
            modal.innerHTML = '';
        }
    }

    document.addEventListener('click', function (e) {
        if (!(e.target instanceof Element)) {
            return;
        }
        var closeTrigger = e.target.closest('[data-modal-close]');
        if (closeTrigger) {
            e.preventDefault();
            e.stopPropagation();
            closeModal();
            return;
        }
        var modal = getModal();
        if (modal && e.target === modal) {
            closeModal();
        }
    }, true);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modalIsOpen()) {
            closeModal();
        }
    });

    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.target && e.target.id === 'modal') {
            focusFirstInModal();
            setupFocusTrap();
        }
    });

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-add-formset-row]');
        if (!btn) {
            return;
        }
        e.preventDefault();

        var prefix = btn.dataset.formsetPrefix;
        var target = document.querySelector(btn.dataset.formsetTarget);
        var template = document.querySelector(btn.dataset.formsetTemplate);
        var totalEl = document.querySelector(
            'input[name="' + prefix + '-TOTAL_FORMS"]'
        );
        if (!target || !template || !totalEl) {
            return;
        }

        var index = parseInt(totalEl.value, 10) || 0;
        var html = template.innerHTML.replace(/__prefix__/g, String(index));
        target.insertAdjacentHTML('beforeend', html);
        totalEl.value = String(index + 1);
    });
})();
