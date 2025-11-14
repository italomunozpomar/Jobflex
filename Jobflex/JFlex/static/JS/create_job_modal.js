document.addEventListener('DOMContentLoaded', function () {
    const createJobModal = document.getElementById('create-job-modal');
    if (!createJobModal) return; // Stop if the modal isn't on the page

    const form = document.getElementById('create-job-form');

    // Reset modal when "Crear Empleo" button is clicked (for creation)
    const createJobBtn = document.querySelector('[data-modal-toggle="create-job-modal"]');
    if (createJobBtn) {
        createJobBtn.addEventListener('click', function() {
            // Reset to create mode
            document.getElementById('offer-id-input').value = '';
            document.getElementById('form-action').value = 'create_job_offer';
            document.getElementById('modal-title').textContent = 'Crear Nueva Oferta Laboral';
            document.getElementById('submit-btn').textContent = 'Publicar Oferta';
            // Clear the stored publication date
            delete form.dataset.fechaPublicacion;

            // Reset location fields
            const regionSelect = form.querySelector('[name=region]');
            const ciudadSelect = form.querySelector('[name=ciudad]');
            regionSelect.value = ''; // Clear region selection
            ciudadSelect.innerHTML = '<option value="">Selecciona una ciudad</option>';
            ciudadSelect.value = '';
            
            // Trigger change on regionSelect to re-populate cities and update preview
            regionSelect.dispatchEvent(new Event('change', { bubbles: true }));
        });
    }

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
                    value = '$ ' + value;
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

    // --- Chained Dropdown Logic for Region and Ciudad ---
    const regionSelect = form.querySelector('[name=region]');
    const ciudadSelect = form.querySelector('[name=ciudad]');
    const previewLocation = document.getElementById('preview-location');

    const updateLocationPreview = () => {
        const selectedRegionText = regionSelect.options[regionSelect.selectedIndex]?.text || 'Región';
        const selectedCiudadText = ciudadSelect.options[ciudadSelect.selectedIndex]?.text || 'Ciudad';
        
        if (selectedRegionText === 'Cualquier Región' && selectedCiudadText === 'Cualquier Comuna') {
            previewLocation.innerText = 'Chile';
        } else if (selectedCiudadText === 'Cualquier Comuna' && selectedRegionText !== 'Cualquier Región') {
            // If a specific region is selected and city is "Cualquier Comuna", show only the region
            previewLocation.innerText = selectedRegionText;
        } else if (selectedRegionText && selectedCiudadText) {
            previewLocation.innerText = `${selectedCiudadText}, ${selectedRegionText}`;
        } else if (selectedRegionText) {
            previewLocation.innerText = selectedRegionText;
        } else {
            previewLocation.innerText = 'Ubicación';
        }
    };

    const populateCities = async (regionId, selectedCiudadId = null) => {
        ciudadSelect.innerHTML = '<option value="">Cargando ciudades...</option>';
        ciudadSelect.disabled = true; // Disable while loading

        if (!regionId) {
            ciudadSelect.innerHTML = '<option value="">Selecciona una región</option>';
            ciudadSelect.disabled = false;
            updateLocationPreview(); // Update preview when region is cleared
            return;
        }
        try {
            const response = await fetch(`/ajax/ciudades/${regionId}/`);
            const cities = await response.json();
            
            ciudadSelect.innerHTML = ''; // Clear previous options
            
            if (cities.length === 0) {
                ciudadSelect.innerHTML = '<option value="">No hay ciudades disponibles</option>';
            } else {
                cities.forEach(city => {
                    const option = document.createElement('option');
                    option.value = city.id_ciudad; // Use id_ciudad as value
                    option.textContent = city.nombre;
                    ciudadSelect.appendChild(option);
                });
            }
            
            if (selectedCiudadId) {
                ciudadSelect.value = selectedCiudadId;
            } else {
                // Set "Cualquier comuna" as default if available and it's the only option
                const cualquierComunaOption = Array.from(ciudadSelect.options).find(option => option.textContent === 'Cualquier comuna');
                if (cualquierComunaOption && cities.length === 1) { // Only auto-select if it's the only city
                    ciudadSelect.value = cualquierComunaOption.value;
                } else if (cities.length > 0) {
                    ciudadSelect.value = cities[0].id_ciudad; // Select the first city by default
                }
            }
            ciudadSelect.disabled = false; // Re-enable after loading
            updateLocationPreview(); // Update preview after cities are populated

        } catch (error) {
            console.error('Error fetching cities:', error);
            ciudadSelect.innerHTML = '<option value="">Error al cargar ciudades</option>';
            ciudadSelect.disabled = false;
            updateLocationPreview(); // Update preview on error
        }
    };

    if (regionSelect && ciudadSelect) {
        regionSelect.addEventListener('change', (event) => {
            populateCities(event.target.value);
        });
        ciudadSelect.addEventListener('change', updateLocationPreview); // Update preview when city changes
    }

    // Initial population and preview update
    if (regionSelect.value) {
        populateCities(regionSelect.value);
    } else {
        updateLocationPreview(); // Initial preview update if no region is selected
    }


    // --- Helper function to populate offer fields ---
    const populateOfferFields = (button) => {
        function setFieldValue(selector, value) {
            const element = form.querySelector(selector);
            if (element) {
                element.value = value;
            }
        }

        // Store publication date for later use in date calculations
        form.dataset.fechaPublicacion = button.dataset.fechaPublicacion;

        // 1. Populate all fields
        setFieldValue('[name=titulo_puesto]', button.dataset.titulo);
        setFieldValue('[name=salario_min]', button.dataset.salarioMin);
        setFieldValue('[name=salario_max]', button.dataset.salarioMax);
        setFieldValue('[name=nivel_experiencia]', button.dataset.nivelExperiencia);
        setFieldValue('[name=categoria]', button.dataset.categoriaId);
        setFieldValue('[name=jornada]', button.dataset.jornadaId);
        setFieldValue('[name=modalidad]', button.dataset.modalidadId);
        
        // Populate Region and then Cities
        const initialRegionId = button.dataset.regionId;
        const initialCiudadId = button.dataset.ciudadId;

        setFieldValue('[name=region]', initialRegionId);
        // Trigger change event to populate cities for the selected region
        if (initialRegionId) {
            populateCities(initialRegionId, initialCiudadId);
        } else {
            // If no region is set, clear cities and update preview
            ciudadSelect.innerHTML = '<option value="">Selecciona una región</option>';
            ciudadSelect.value = '';
            updateLocationPreview();
        }

        // Handle duration and custom date
        const duracion = button.dataset.duracionOferta;
        setFieldValue('[name=duracion_oferta]', duracion);

        if (duracion === 'custom') {
            setFieldValue('[name=fecha_cierre_personalizada]', button.dataset.fechaCierre);
        }

        // Manually trigger the change event on the duration select to show/hide the custom date field
        form.querySelector('[name=duracion_oferta]').dispatchEvent(new Event('change', { bubbles: true }));

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

        // Trigger previews for all fields
        form.querySelectorAll('input, select').forEach(el => {
            const eventType = el.tagName === 'SELECT' ? 'change' : 'input';
            el.dispatchEvent(new Event(eventType, { bubbles: true }));
        });
        updateLocationPreview(); // Ensure location preview is updated after populating fields
    };

    // --- DUPLICATE OFFER LOGIC ---
    document.addEventListener('click', function(event) {
        const button = event.target.closest('.duplicate-offer-btn');
        if (button) {
            // Clear the offer_id to create a new one
            document.getElementById('offer-id-input').value = '';
            document.getElementById('form-action').value = 'create_job_offer';
            document.getElementById('modal-title').textContent = 'Crear Nueva Oferta Laboral';
            document.getElementById('submit-btn').textContent = 'Publicar Oferta';
            delete form.dataset.fechaPublicacion;
            
            populateOfferFields(button);

            // 4. Open the modal
            createJobModal.classList.remove('hidden');
        }
    });

    // --- EDIT OFFER LOGIC ---
    document.addEventListener('click', function(event) {
        const button = event.target.closest('.edit-offer-btn');
        if (button) {
            const offerId = button.dataset.offerId;
            
            // Set the offer_id and change action to edit_job_offer
            document.getElementById('offer-id-input').value = offerId;
            document.getElementById('form-action').value = 'edit_job_offer';
            document.getElementById('modal-title').textContent = 'Editar Oferta Laboral';
            document.getElementById('submit-btn').textContent = 'Guardar Cambios';
            
            populateOfferFields(button);

            // Open the modal
            createJobModal.classList.remove('hidden');
        }
    });

    // --- CLEAR FORM LOGIC ---
    const clearFormBtn = document.getElementById('clear-form-btn');
    if (clearFormBtn) {
        clearFormBtn.addEventListener('click', function() {
            form.reset();
            document.getElementById('offer-id-input').value = '';
            document.getElementById('form-action').value = 'create_job_offer';
            document.getElementById('modal-title').textContent = 'Crear Nueva Oferta Laboral';
            document.getElementById('submit-btn').textContent = 'Publicar Oferta';
            delete form.dataset.fechaPublicacion;
            
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
            // Reset location fields
            const regionSelect = form.querySelector('[name=region]');
            const ciudadSelect = form.querySelector('[name=ciudad]');
            regionSelect.value = '';
            ciudadSelect.innerHTML = '<option value="">Selecciona una ciudad</option>';
            ciudadSelect.value = '';
            updateLocationPreview(); // Update preview after clearing form
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
                
                const formatDate = (d) => d.toISOString().split('T')[0];
                
                // Determine the start date for validation (publication date or today)
                let startDate;
                if (form.dataset.fechaPublicacion) {
                    startDate = new Date(form.dataset.fechaPublicacion + 'T00:00:00');
                } else {
                    startDate = new Date();
                }
                customDateInput.min = formatDate(startDate);

                // Calculate the standard maximum date (30 days from start)
                const standardMaxDate = new Date(startDate);
                standardMaxDate.setDate(startDate.getDate() + 30);

                // Check if there's an existing closing date in the input
                const existingClosingDateValue = customDateInput.value;
                if (existingClosingDateValue) {
                    // The value is already in YYYY-MM-DD format
                    const existingClosingDate = new Date(existingClosingDateValue + 'T00:00:00');
                    
                    // If the existing date is after the standard max date, use it as the max
                    if (existingClosingDate > standardMaxDate) {
                        customDateInput.max = formatDate(existingClosingDate);
                        return; // Exit early, validation is set
                    }
                }
                
                // Otherwise, use the standard 30-day max date
                customDateInput.max = formatDate(standardMaxDate);

            } else {
                customDateContainer.classList.add('hidden');
            }
        });
    }
});