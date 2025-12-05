document.addEventListener('DOMContentLoaded', function () {
    const createJobModal = document.getElementById('create-job-modal');
    if (!createJobModal) return;

    const form = document.getElementById('create-job-form');
    const submitBtn = document.getElementById('submit-btn');
    const modalTitle = document.getElementById('modal-title');
    const formAction = document.getElementById('form-action');
    const offerIdInput = document.getElementById('offer-id-input');

    // Mobile Navigation Elements
    const prevStepBtn = document.getElementById('mobile-prev-btn');
    const nextStepBtn = document.getElementById('mobile-next-btn');
    const mobileSubmitBtn = document.getElementById('mobile-submit-btn');
    const mobilePreviewToggle = document.getElementById('mobile-preview-toggle');
    const mobileStepIndicator = document.getElementById('mobile-step-indicator');
    const stepDots = document.querySelectorAll('.step-dot');
    const formSteps = document.querySelectorAll('.form-step');
    const previewContainer = document.getElementById('preview-container');
    const closePreviewMobileBtn = document.getElementById('close-preview-mobile-btn');
    const formStepsContainer = document.getElementById('form-steps-container');

    let currentStep = 1;
    const totalSteps = formSteps.length;

    // --- MOBILE STEP LOGIC ---
    function updateStep(step) {
        // Only execute step logic if we are on a small screen (mobile view)
        // On desktop (lg), we want everything visible simultaneously.
        const isMobile = window.innerWidth < 1024; 

        if (!isMobile) {
            // Desktop: ensure all steps are visible (remove 'hidden' that might have been added by mobile logic)
            formSteps.forEach(el => {
                el.classList.remove('hidden');
                el.classList.add('block');
            });
            return; 
        }

        currentStep = step;
        
        // Show/Hide Steps for Mobile
        formSteps.forEach((el, index) => {
            if (index + 1 === currentStep) {
                el.classList.remove('hidden');
                el.classList.add('block');
            } else {
                el.classList.add('hidden');
                el.classList.remove('block');
            }
        });

        // Update Indicator Text
        if (mobileStepIndicator) {
            mobileStepIndicator.textContent = `Paso ${currentStep} de ${totalSteps}`;
        }

        // Update Dots
        stepDots.forEach(dot => {
            const dotStep = parseInt(dot.dataset.step);
            if (dotStep <= currentStep) {
                dot.classList.remove('bg-gray-300');
                dot.classList.add('bg-primary');
            } else {
                dot.classList.remove('bg-primary');
                dot.classList.add('bg-gray-300');
            }
        });

        // Update Buttons
        if (prevStepBtn) {
            if (currentStep === 1) {
                prevStepBtn.classList.add('hidden');
            } else {
                prevStepBtn.classList.remove('hidden');
            }
        }

        if (nextStepBtn && mobileSubmitBtn) {
            if (currentStep === totalSteps) {
                nextStepBtn.classList.add('hidden');
                mobileSubmitBtn.classList.remove('hidden');
            } else {
                nextStepBtn.classList.remove('hidden');
                mobileSubmitBtn.classList.add('hidden');
            }
        }
        
        // Scroll to top of form container on step change
        if (formStepsContainer) {
            formStepsContainer.scrollTop = 0;
        }
    }

    // Simple Validation per Step
    function validateStep(step) {
        // Skip validation if on desktop, user can see everything
        if (window.innerWidth >= 1024) return true;

        const currentStepEl = document.querySelector(`.form-step:nth-child(${step})`);
        if (!currentStepEl) return true;

        const requiredInputs = currentStepEl.querySelectorAll('input[required], select[required], textarea[required]');
        let isValid = true;

        requiredInputs.forEach(input => {
            if (!input.value.trim()) {
                isValid = false;
                input.classList.add('border-red-500');
                input.addEventListener('input', function() {
                    this.classList.remove('border-red-500');
                }, { once: true });
            }
        });

        // Special handling for Quill editors
        if (step === 2) { // "Detalles del Puesto" is step 2 in the new order?
            // Wait, in HTML:
            // Step 1: Info
            // Step 2: Detalles (Quill)
            // Step 3: Condiciones
            // Step 4: Habilidades
            
            // Check if current step contains quill editors
            if (currentStepEl.querySelector('#quill-descripcion')) {
                 const descText = quillDescripcion.getText().trim();
                 if (descText.length === 0) {
                     isValid = false;
                     document.getElementById('quill-descripcion').style.border = '1px solid red';
                 } else {
                     document.getElementById('quill-descripcion').style.border = 'none';
                 }
            }
        }

        return isValid;
    }

    if (prevStepBtn) {
        prevStepBtn.addEventListener('click', () => {
            if (currentStep > 1) updateStep(currentStep - 1);
        });
    }

    if (nextStepBtn) {
        nextStepBtn.addEventListener('click', () => {
            if (validateStep(currentStep)) {
                if (currentStep < totalSteps) updateStep(currentStep + 1);
            }
        });
    }

    // --- MOBILE PREVIEW LOGIC ---
    if (mobilePreviewToggle && previewContainer) {
        mobilePreviewToggle.addEventListener('click', () => {
            previewContainer.classList.remove('hidden');
            // Ensure it's visible even if lg:block is confusing things (mobile override)
            previewContainer.classList.add('block'); 
        });
    }

    if (closePreviewMobileBtn && previewContainer) {
        closePreviewMobileBtn.addEventListener('click', () => {
            previewContainer.classList.add('hidden');
            previewContainer.classList.remove('block');
        });
    }

    // Handle Resize events
    window.addEventListener('resize', () => {
        updateStep(currentStep);
    });


    // --- RESET LOGIC ---
    function resetModal() {
        form.reset();
        offerIdInput.value = '';
        formAction.value = 'create_job_offer';
        modalTitle.textContent = 'Crear Nueva Oferta Laboral';
        if (submitBtn) submitBtn.textContent = 'Publicar Oferta';
        if (mobileSubmitBtn) mobileSubmitBtn.textContent = 'Publicar Oferta';
        delete form.dataset.fechaPublicacion;

        quillDescripcion.setText('');
        quillRequisitos.setText('');
        tagifyHabilidades.removeAllTags();
        tagifyBeneficios.removeAllTags();

        // Reset Previews
        document.getElementById('preview-titulo').textContent = 'Título de la Oferta';
        document.getElementById('preview-categoria').textContent = 'Categoría';
        // Reset others manually if needed or trigger events
        
        // Reset Location
        const regionSelect = form.querySelector('[name=region]');
        const ciudadSelect = form.querySelector('[name=ciudad]');
        if (regionSelect) regionSelect.value = '';
        if (ciudadSelect) {
            ciudadSelect.innerHTML = '<option value="">Selecciona una ciudad</option>';
            ciudadSelect.value = '';
        }
        updateLocationPreview();

        // Reset Step
        updateStep(1);
        if (previewContainer && window.innerWidth < 1024) {
            previewContainer.classList.add('hidden');
            previewContainer.classList.remove('block');
        }
    }

    const createJobBtn = document.querySelector('[data-modal-toggle="create-job-modal"]');
    if (createJobBtn) {
        createJobBtn.addEventListener('click', resetModal);
    }

    // --- EXISTING LOGIC (Quill, Tagify, etc.) ---
    
    const quillDescripcion = new Quill('#quill-descripcion', {
        theme: 'snow',
        placeholder: 'Describe las responsabilidades y el propósito del puesto...'
    });
    const quillRequisitos = new Quill('#quill-requisitos', {
        theme: 'snow',
        placeholder: 'Detalla la experiencia, educación y habilidades necesarias...'
    });

    quillDescripcion.on('text-change', () => {
       document.getElementById('quill-descripcion').style.border = 'none';
    });

    const tagifyHabilidades = new Tagify(form.querySelector('input[name=habilidades_clave]'));
    const tagifyBeneficios = new Tagify(form.querySelector('input[name=beneficios]'));

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

    let isPopulating = false; 

    const regionSelect = form.querySelector('[name=region]');
    const ciudadSelect = form.querySelector('[name=ciudad]');
    const previewLocation = document.getElementById('preview-location');

    const updateLocationPreview = () => {
        const selectedRegionText = regionSelect.options[regionSelect.selectedIndex]?.text || 'Región';
        const selectedCiudadText = ciudadSelect.options[ciudadSelect.selectedIndex]?.text || 'Ciudad';
        
        if (selectedRegionText === 'Cualquier Región' && selectedCiudadText === 'Cualquier Comuna') {
            previewLocation.innerText = 'Chile';
        } else if (selectedCiudadText === 'Cualquier Comuna' && selectedRegionText !== 'Cualquier Región') {
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
        ciudadSelect.disabled = true;

        if (!regionId) {
            ciudadSelect.innerHTML = '<option value="">Selecciona una región</option>';
            ciudadSelect.disabled = false;
            updateLocationPreview();
            return;
        }
        try {
            const response = await fetch(`/ajax/ciudades/${regionId}/`);
            const cities = await response.json();
            
            ciudadSelect.innerHTML = '';
            
            if (cities.length === 0) {
                ciudadSelect.innerHTML = '<option value="">No hay ciudades disponibles</option>';
            } else {
                cities.forEach(city => {
                    const option = document.createElement('option');
                    option.value = city.id_ciudad;
                    option.textContent = city.nombre;
                    ciudadSelect.appendChild(option);
                });
            }
            
            if (selectedCiudadId) {
                ciudadSelect.value = selectedCiudadId;
            }
            ciudadSelect.disabled = false;
            updateLocationPreview();

        } catch (error) {
            console.error('Error fetching cities:', error);
            ciudadSelect.innerHTML = '<option value="">Error al cargar ciudades</option>';
            ciudadSelect.disabled = false;
            updateLocationPreview();
        }
    };

    if (regionSelect && ciudadSelect) {
        regionSelect.addEventListener('change', (event) => {
            if (isPopulating) return;
            populateCities(event.target.value);
        });
        ciudadSelect.addEventListener('change', updateLocationPreview);
    }

    if (regionSelect.value) {
        populateCities(regionSelect.value);
    } else {
        updateLocationPreview();
    }

    const populateOfferFields = async (button) => {
        isPopulating = true;

        function setFieldValue(selector, value) {
            const element = form.querySelector(selector);
            if (element) {
                element.value = value;
            }
        }

        form.dataset.fechaPublicacion = button.dataset.fechaPublicacion;

        setFieldValue('[name=titulo_puesto]', button.dataset.titulo);
        setFieldValue('[name=salario_min]', button.dataset.salarioMin);
        setFieldValue('[name=salario_max]', button.dataset.salarioMax);
        setFieldValue('[name=nivel_experiencia]', button.dataset.nivelExperiencia);
        setFieldValue('[name=categoria]', button.dataset.categoriaId);
        setFieldValue('[name=jornada]', button.dataset.jornadaId);
        setFieldValue('[name=modalidad]', button.dataset.modalidadId);
        
        const initialRegionId = button.dataset.regionId;
        const initialCiudadId = button.dataset.ciudadId;

        setFieldValue('[name=region]', initialRegionId);
        
        if (initialRegionId) {
            await populateCities(initialRegionId, initialCiudadId);
        } else {
            ciudadSelect.innerHTML = '<option value="">Selecciona una región</option>';
            ciudadSelect.value = '';
            updateLocationPreview();
        }

        const duracion = button.dataset.duracionOferta;
        setFieldValue('[name=duracion_oferta]', duracion);

        if (duracion === 'custom') {
            setFieldValue('[name=fecha_cierre_personalizada]', button.dataset.fechaCierre);
        }

        form.querySelector('[name=duracion_oferta]').dispatchEvent(new Event('change', { bubbles: true }));

        quillDescripcion.root.innerHTML = button.dataset.descripcion;
        document.getElementById('preview-descripcion').innerHTML = button.dataset.descripcion;
        
        quillRequisitos.root.innerHTML = button.dataset.requisitos;
        document.getElementById('preview-requisitos').innerHTML = button.dataset.requisitos;

        tagifyHabilidades.removeAllTags();
        if (button.dataset.habilidades) tagifyHabilidades.addTags(button.dataset.habilidades.split(','));
        
        tagifyBeneficios.removeAllTags();
        if (button.dataset.beneficios) tagifyBeneficios.addTags(button.dataset.beneficios.split(','));

        form.querySelectorAll('input, select').forEach(el => {
            const eventType = el.tagName === 'SELECT' ? 'change' : 'input';
            el.dispatchEvent(new Event(eventType, { bubbles: true }));
        });
        updateLocationPreview();
        
        isPopulating = false;
    };

    const openModalWithData = async (button, action, title, submitText) => {
        offerIdInput.value = button.dataset.offerId || '';
        if (action === 'create_job_offer') offerIdInput.value = '';

        formAction.value = action;
        modalTitle.textContent = title;
        if(submitBtn) submitBtn.textContent = submitText;
        if(mobileSubmitBtn) mobileSubmitBtn.textContent = submitText;
        
        if (action === 'create_job_offer') delete form.dataset.fechaPublicacion;
        
        await populateOfferFields(button);
        
        createJobModal.classList.remove('hidden');
        updateStep(1);
    };

    document.addEventListener('click', async function(event) {
        const dupBtn = event.target.closest('.duplicate-offer-btn');
        if (dupBtn) {
            await openModalWithData(dupBtn, 'create_job_offer', 'Crear Nueva Oferta Laboral', 'Publicar Oferta');
        }

        const editBtn = event.target.closest('.edit-offer-btn');
        if (editBtn) {
            await openModalWithData(editBtn, 'edit_job_offer', 'Editar Oferta Laboral', 'Guardar Cambios');
        }
    });

    const clearFormBtn = document.getElementById('clear-form-btn');
    if (clearFormBtn) {
        clearFormBtn.addEventListener('click', resetModal);
    }

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
    
    const duracionSelect = document.getElementById('id_duracion_oferta');
    if (duracionSelect) {
        const customDateContainer = document.getElementById('custom-date-container');
        const customDateInput = document.getElementById('id_fecha_cierre_personalizada');
        duracionSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customDateContainer.classList.remove('hidden');
                
                const formatDate = (d) => d.toISOString().split('T')[0];
                
                let startDate;
                if (form.dataset.fechaPublicacion) {
                    startDate = new Date(form.dataset.fechaPublicacion + 'T00:00:00');
                } else {
                    startDate = new Date();
                }
                customDateInput.min = formatDate(startDate);

                const standardMaxDate = new Date(startDate);
                standardMaxDate.setDate(startDate.getDate() + 30);

                const existingClosingDateValue = customDateInput.value;
                if (existingClosingDateValue) {
                    const existingClosingDate = new Date(existingClosingDateValue + 'T00:00:00');
                    if (existingClosingDate > standardMaxDate) {
                        customDateInput.max = formatDate(existingClosingDate);
                        return;
                    }
                }
                customDateInput.max = formatDate(standardMaxDate);

            } else {
                customDateContainer.classList.add('hidden');
            }
        });
    }
    
    // Init
    updateStep(1);
});