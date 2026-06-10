/** Toggle every row checkbox in the same dashboard box. */
function applyBulkSelectAll(selectAll) {
    var box = selectAll && selectAll.closest ? selectAll.closest('.box') : null;
    if (!box) {
        return;
    }
    var checked = selectAll.checked;
    box.querySelectorAll('[data-bulk-item]').forEach(function (item) {
        item.checked = checked;
    });
    selectAll.indeterminate = false;
}

(function () {
    'use strict';

    var focusTrapHandler = null;
    var pendingSortFocusKey = null;

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

    function getBulkBox(el) {
        return el && el.closest ? el.closest('.box') : null;
    }

    function syncBulkSelectAll(box) {
        if (!box) {
            return;
        }
        var selectAll = box.querySelector('[data-bulk-select-all]');
        if (!selectAll) {
            return;
        }
        var items = box.querySelectorAll('[data-bulk-item]');
        if (items.length === 0) {
            selectAll.checked = false;
            selectAll.indeterminate = false;
            selectAll.disabled = true;
            return;
        }
        selectAll.disabled = false;
        var checkedCount = box.querySelectorAll('[data-bulk-item]:checked').length;
        selectAll.checked = checkedCount === items.length;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < items.length;
    }

    function initBulkBox(box) {
        syncBulkSelectAll(box);
    }

    function initBulkForms(root) {
        var scope = root || document;
        if (scope.classList && scope.classList.contains('box')) {
            initBulkBox(scope);
            return;
        }
        scope.querySelectorAll('.box').forEach(initBulkBox);
    }

    document.addEventListener('change', function (e) {
        if (!(e.target instanceof Element)) {
            return;
        }
        var box = getBulkBox(e.target);
        if (!box) {
            return;
        }
        if (e.target.matches('[data-bulk-select-all]')) {
            applyBulkSelectAll(e.target);
            return;
        }
        if (e.target.matches('[data-bulk-item]')) {
            syncBulkSelectAll(box);
        }
    });

    document.body.addEventListener('htmx:beforeRequest', function (e) {
        var elt = e.detail && e.detail.elt;
        if (elt && elt.matches && elt.matches('.list-table__sort-btn')) {
            pendingSortFocusKey = elt.getAttribute('data-sort-key');
        }
    });

    document.body.addEventListener('htmx:confirm', function (e) {
        var elt = e.detail && e.detail.elt;
        if (!elt || !elt.matches('[data-bulk-delete]')) {
            return;
        }
        var form = elt.closest('[data-bulk-form]');
        if (!form || form.querySelectorAll('[data-bulk-item]:checked').length === 0) {
            e.preventDefault();
        }
    });

    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.target && e.target.id === 'modal') {
            focusFirstInModal();
            setupFocusTrap();
        }
        if (e.target && e.target.classList && e.target.classList.contains('box__list')) {
            var box = e.target.closest('.box');
            initBulkBox(box);
            if (e.target.id === 'box-courses-list' && pendingSortFocusKey) {
                var sortBtn = e.target.querySelector(
                    '.list-table__sort-btn[data-sort-key="' + pendingSortFocusKey + '"]'
                );
                if (sortBtn) {
                    sortBtn.focus({ preventScroll: true });
                }
                pendingSortFocusKey = null;
            }
        }
    });

    initBulkForms(document);

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

        if (prefix === 'requirements') {
            var usedOrders = [];
            target.querySelectorAll('input[name$="-display_order"]').forEach(function (input) {
                var value = parseInt(input.value, 10);
                if (!isNaN(value)) {
                    usedOrders.push(value);
                }
            });
            var nextOrder = 0;
            while (usedOrders.indexOf(nextOrder) !== -1) {
                nextOrder += 1;
            }
            var newRow = target.lastElementChild;
            if (newRow) {
                var orderInput = newRow.querySelector('input[name$="-display_order"]');
                if (orderInput) {
                    orderInput.value = String(nextOrder);
                }
            }
        }
    });
})();
