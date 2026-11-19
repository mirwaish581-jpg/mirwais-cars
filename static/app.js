
// ==============================
// د موټر معلومات په فورم کې ښکاره کول
// ==============================

function editCar(c) {
    const fields = [
        'name',
        'brand',
        'model',
        'year',
        'price',
        'mileage',
        'fuel',
        'transmission',
        'category',
        'color',
        'condition',
        'status',
        'description',
        'engine',
        'drive',
        'doors',
        'seats',
        'vin',
        'features'
    ];

    // د موټر ID
    const idField = document.getElementById('carid');
    if (idField) {
        idField.value = c.id ?? '';
    }

    // د ټولو مشخصاتو ډکول
    fields.forEach(function (key) {
        const element = document.getElementById(key);

        if (element) {
            element.value = c[key] ?? '';
        }
    });

    // د عکسونو انتخاب تش پرېږده
    const imageInput = document.getElementById('images');
    if (imageInput) {
        imageInput.value = '';
    }

    const imageCount = document.getElementById('imageCount');
    const imagePreview = document.getElementById('imagePreview');

    if (imageCount) {
        imageCount.textContent =
            'د نوي عکسونو انتخاب اختیاري دی؛ تر ۱۰ پورې عکسونه انتخاب کړئ.';
    }

    if (imagePreview) {
        imagePreview.innerHTML = '';
    }

    // فورم ته پورته تلل
    const form = document.getElementById('carForm');

    if (form) {
        form.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}


// ==============================
// د نوي موټر لپاره فورم پاکول
// ==============================

function clearCarForm() {
    const form = document.getElementById('carForm');

    if (form) {
        form.reset();
    }

    const idField = document.getElementById('carid');
    if (idField) {
        idField.value = '';
    }

    const imageInput = document.getElementById('images');
    if (imageInput) {
        imageInput.value = '';
    }

    const imageCount = document.getElementById('imageCount');
    if (imageCount) {
        imageCount.textContent = 'تر اوسه عکس نه دی انتخاب شوی.';
    }

    const imagePreview = document.getElementById('imagePreview');
    if (imagePreview) {
        imagePreview.innerHTML = '';
    }

    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}
