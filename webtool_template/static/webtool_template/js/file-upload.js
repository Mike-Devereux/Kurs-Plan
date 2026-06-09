/**
 * Custom file-upload trigger extracted from Chem-E tutorial/exercise pages.
 *
 * Usage:
 *   <form enctype="multipart/form-data" data-webtool-file-upload>
 *     <input type="hidden" name="force_replace_graded_upload" value="0">
 *     {% include "webtool_template/components/file_upload_field.html" with ... %}
 *   </form>
 *   <script src="{% static 'webtool_template/js/file-upload.js' %}"></script>
 */
(() => {
    const DEFAULT_EMPTY_LABEL = "keine ausgewählte Datei";
    const DEFAULT_CONFIRM_MESSAGE =
        "Do you really want to upload a new file? Any existing file and any existing grade will be overwritten!";

    function initForm(form) {
        const forceReplaceInput = form.querySelector("input[name='force_replace_graded_upload']");
        const confirmMessage = form.dataset.uploadConfirm || DEFAULT_CONFIRM_MESSAGE;
        const emptyLabel = form.dataset.uploadEmptyLabel || DEFAULT_EMPTY_LABEL;

        form.querySelectorAll("button[data-upload-trigger]").forEach((button) => {
            const inputId = button.getAttribute("data-upload-trigger");
            const input = form.querySelector(`#${CSS.escape(inputId)}`);
            const nameDisplay = form.querySelector(`#${CSS.escape(inputId)}_name`);
            if (!input || !nameDisplay) {
                return;
            }

            button.addEventListener("click", () => {
                const hasExistingUpload = input.dataset.hasExistingUpload === "1";
                if (forceReplaceInput) {
                    forceReplaceInput.value = "0";
                }
                if (hasExistingUpload) {
                    if (!window.confirm(confirmMessage)) {
                        return;
                    }
                    if (forceReplaceInput) {
                        forceReplaceInput.value = "1";
                    }
                }
                input.click();
            });

            input.addEventListener("change", () => {
                if (input.files && input.files.length > 0) {
                    nameDisplay.textContent = input.files[0].name;
                } else {
                    nameDisplay.textContent = emptyLabel;
                }
            });
        });
    }

    document
        .querySelectorAll("form[enctype='multipart/form-data'][data-webtool-file-upload], form[enctype='multipart/form-data']")
        .forEach(initForm);
})();
