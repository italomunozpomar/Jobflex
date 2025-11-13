document.addEventListener('DOMContentLoaded', function () {
    const createJobModal = document.getElementById('create-job-modal');
    if (!createJobModal) return; // Stop if the modal isn't on the page

    const form = document.getElementById('create-job-form');

    // Quill Editors
    const quillDescripcion = new Quill('#quill-descripcion', {
        theme: 'snow',
        placeholder: 'Describe las responsabilidades y el propósito del puesto...'
    });
    const quillRequisitos = new Quill('#quill-requisitos', {
        theme: 'snow',
        placeholder: 'Detalla la experiencia, educación y habilidades necesarias...'
    });

    // Tagify Inputs
    const tagifyHabilidades = new Tagify(form.querySelector('input[name=habilidades_clave]'));
    const tagifyBeneficios = new Tagify(form.querySelector('input[name=beneficios]'));

    // --- LIVE PREVIEW LOGIC ---
    const hiddenDesc = form.querySelector('textarea[name=descripcion_puesto]');
    const hiddenReq = form.querySelector('textarea[name=requisitos_puesto]');
    hiddenDesc.style.display = 'none';
    hiddenReq.style.display = 'none';

    const fieldsToSync = {
        'titulo_puesto': { target: 'preview-titulo', default: 'Título de la Oferta' },
        'categoria': { target: 'preview-categoria', default: 'Categoría', isSelect: true },
        'salario_min': { target: 'preview-sal-min', default: 'Salario Min' },
        'salario_max': { target: 'preview-sal-max', default: 'Salario Max' },
        'modalidad': { target: 'preview-modalidad', default: 'Modalidad', isSelect: true },
        'jornada': { target: 'preview-jornada', default: 'Jornada', isSelect: true },
        'nivel_experiencia': { target: 'preview-experiencia', default: 'Experiencia' },
    };

    const handlePreviewUpdate = (e) => {
        const fieldName = e.target.name;
        if (fieldsToSync[fieldName]) {
            const config = fieldsToSync[fieldName];
            const previewEl = document.getElementById(config.target);
            if (!previewEl) return;

            let value = e.target.value;

            if (config.isSelect) {
                value = (e.target.selectedIndex >= 0) ? e.target.options[e.target.selectedIndex].text : '';
            } else if (fieldName === 'salario_min' || fieldName === 'salario_max') {
                const num = parseInt(String(value).replace(/\./g, ''), 10);
                value = !isNaN(num) ? new Intl.NumberFormat('es-CL').format(num) : '';
                if (value) {
                    value = '$' + value;
                }
            }
            previewEl.innerText = value || config.default;
        }
    };

    form.addEventListener('input', handlePreviewUpdate);
    form.addEventListener('change', handlePreviewUpdate);

    quillDescripcion.on('text-change', () => {
        const html = quillDescripcion.root.innerHTML;
        document.getElementById('preview-descripcion').innerHTML = html;
        hiddenDesc.value = html;
    });
    quillRequisitos.on('text-change', () => {
        const html = quillRequisitos.root.innerHTML;
        document.getElementById('preview-requisitos').innerHTML = html;
        hiddenReq.value = html;
    });

    const updateTagsPreview = (tags, previewId, isBenefit) => {
        const container = document.getElementById(previewId);
        container.innerHTML = '';
        if (tags.length === 0) {
            const span = document.createElement('span');
            span.className = isBenefit
                ? 'bg-green-100 text-green-800 text-xs font-semibold px-2.5 py-0.5 rounded-full'
                : 'bg-gray-200 text-gray-800 text-xs font-semibold px-2.5 py-0.5 rounded-full';
            span.innerText = isBenefit ? 'Beneficio 1' : 'Habilidad 1';
            container.appendChild(span);
            return;
        }
        tags.forEach(tag => {
            const span = document.createElement('span');
            span.className = isBenefit
                ? 'bg-green-100 text-green-800 text-xs font-semibold px-2.5 py-0.5 rounded-full'
                : 'bg-gray-200 text-gray-800 text-xs font-semibold px-2.5 py-0.5 rounded-full';
            span.innerText = tag.value;
            container.appendChild(span);
        });
    };
    tagifyHabilidades.on('change', (e) => updateTagsPreview(e.detail.tagify.value, 'preview-habilidades', false));
    tagifyBeneficios.on('change', (e) => updateTagsPreview(e.detail.tagify.value, 'preview-beneficios', true));

    // --- DUPLICATE OFFER LOGIC ---
    document.addEventListener('click', function(event) {
        if (event.target.classList.contains('duplicate-offer-btn')) {
            const button = event.target;
            
            function populateAndTrigger(selector, value) {
                const element = form.querySelector(selector);
                console.log(`Populating field. Selector: "${selector}", Value: "${value}"`);

                if (!element) {
                    console.error(`   [Error] Element not found for selector.`);
                    return;
                }

                if (element.tagName === 'SELECT') {
                    let found = false;
                    // Iterate through options to find a match by value
                    for (let i = 0; i < element.options.length; i++) {
                        if (element.options[i].value === String(value)) {
                            element.selectedIndex = i;
                            found = true;
                            break;
                        }
                    }
                    if (!found && value === "") {
                        // If value is empty and no direct match, try to select the empty option (usually the first one)
                        for (let i = 0; i < element.options.length; i++) {
                            if (element.options[i].value === "") {
                                element.selectedIndex = i;
                                found = true;
                                break;
                            }
                        }
                    }
                    if (!found) {
                        element.selectedIndex = -1; // No option selected
                    }
                    
                    if (element.selectedIndex !== -1) {
                        console.log(`   [Success] Element value set to "${element.options[element.selectedIndex].value}" (Text: "${element.options[element.selectedIndex].text}").`);
                    } else {
                        console.warn(`   [Warning] No matching option found for value "${value}". Element value is now "${element.value}".`);
                    }

                } else {
                    element.value = value;
                    console.log(`   [Success] Element value set to "${element.value}".`);
                }

                // Dispatch the correct event to trigger previews or other dependent logic.
                const eventType = element.tagName === 'SELECT' ? 'change' : 'input';
                element.dispatchEvent(new Event(eventType, { bubbles: true }));
                console.log(`   Dispatched "${eventType}" event.`);
            }

            // 1. Populate all fields
            populateAndTrigger('[name=titulo_puesto]', button.dataset.titulo);
            populateAndTrigger('[name=salario_min]', button.dataset.salarioMin);
            populateAndTrigger('[name=salario_max]', button.dataset.salarioMax);
            populateAndTrigger('[name=nivel_experiencia]', button.dataset.nivelExperiencia);
            populateAndTrigger('[name=categoria]', button.dataset.categoriaId);
            populateAndTrigger('[name=jornada]', button.dataset.jornadaId);
            populateAndTrigger('[name=modalidad]', button.dataset.modalidadId);
            populateAndTrigger('[name=duracion_oferta]', button.dataset.duracionOferta);

            // 2. Populate Quill editors
            quillDescripcion.root.innerHTML = button.dataset.descripcion;
            document.getElementById('preview-descripcion').innerHTML = button.dataset.descripcion;
            
            quillRequisitos.root.innerHTML = button.dataset.requisitos;
            document.getElementById('preview-requisitos').innerHTML = button.dataset.requisitos;

            // 3. Populate Tagify fields
            tagifyHabilidades.removeAllTags();
            if (button.dataset.habilidades) tagifyHabilidades.addTags(button.dataset.habilidades.split(','));
            
            tagifyBeneficios.removeAllTags();
            if (button.dataset.beneficios) tagifyBeneficios.addTags(button.dataset.beneficios.split(','));

            // 4. Open the modal
            createJobModal.classList.remove('hidden');
        }
    });

    // --- CLEAR FORM LOGIC ---
    const clearFormBtn = document.getElementById('clear-form-btn');
    if (clearFormBtn) {
        clearFormBtn.addEventListener('click', function() {
            form.reset();
            quillDescripcion.setText('');
            quillRequisitos.setText('');
            tagifyHabilidades.removeAllTags();
            tagifyBeneficios.removeAllTags();

            // Manually trigger preview updates for all fields after reset
            for (const key in fieldsToSync) {
                const element = form.querySelector(`[name=${key}]`);
                if (element) {
                    const eventType = element.tagName === 'SELECT' ? 'change' : 'input';
                    element.dispatchEvent(new Event(eventType, { bubbles: true }));
                }
            }
            // Manually reset tag previews
            updateTagsPreview([], 'preview-habilidades', false);
            updateTagsPreview([], 'preview-beneficios', true);

            const categoriaCheckbox = document.getElementById('crear-nueva-categoria-checkbox');
            if (categoriaCheckbox.checked) {
                categoriaCheckbox.checked = false;
                categoriaCheckbox.dispatchEvent(new Event('change'));
            }
        });
    }

    // --- Categoria Toggle Logic ---
    const categoriaCheckbox = document.getElementById('crear-nueva-categoria-checkbox');
    if (categoriaCheckbox) {
        const categoriaSelectContainer = document.getElementById('categoria-select-container');
        const nuevaCategoriaContainer = document.getElementById('nueva-categoria-container');
        const categoriaSelect = document.getElementById('id_categoria');
        const nuevaCategoriaInput = document.getElementById('id_nueva_categoria');

        categoriaCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            categoriaSelectContainer.classList.toggle('hidden', isChecked);
            nuevaCategoriaContainer.classList.toggle('hidden', !isChecked);
            categoriaSelect.disabled = isChecked;
            nuevaCategoriaInput.disabled = !isChecked;
            if (isChecked) categoriaSelect.value = ''; else nuevaCategoriaInput.value = '';
        });
        nuevaCategoriaInput.disabled = true;
    }
    
    // --- Custom Duration Logic ---
    const duracionSelect = document.getElementById('id_duracion_oferta');
    if (duracionSelect) {
        const customDateContainer = document.getElementById('custom-date-container');
        const customDateInput = document.getElementById('id_fecha_cierre_personalizada');
        duracionSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customDateContainer.classList.remove('hidden');
                const today = new Date();
                const maxDate = new Date();
                maxDate.setDate(today.getDate() + 30);
                const formatDate = (d) => d.toISOString().split('T')[0];
                customDateInput.min = formatDate(today);
                customDateInput.max = formatDate(maxDate);
            } else {
                customDateContainer.classList.add('hidden');
            }
        });
    }
});