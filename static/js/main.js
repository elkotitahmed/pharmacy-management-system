// دوال مساعدة عامة
function formatDate(dateString) {
    let d = new Date(dateString);
    return d.toLocaleDateString('ar-EG');
}

function showMessage(msg, type = 'success') {
    let div = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">${msg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
    $('#message-area').html(div);
    setTimeout(() => $('.alert').alert('close'), 3000);
}

// تحميل الأصناف في أي قائمة منسدلة
function loadItemsToSelect(selector, selectedId = null) {
    $.get('/api/items', function(items) {
        let html = '';
        items.forEach(item => {
            html += `<option value="${item.id}" ${selectedId == item.id ? 'selected' : ''}>${item.name} (${item.code})</option>`;
        });
        $(selector).html(html);
    });
}

// توليد خيارات الأصناف لاستخدامها في الجداول الديناميكية
function generateItemOptions(selectedId = null) {
    let opts = '';
    if (window.itemsList) {
        window.itemsList.forEach(item => {
            opts += `<option value="${item.id}" ${selectedId == item.id ? 'selected' : ''}>${item.name}</option>`;
        });
    }
    return opts;
}

// تحميل قائمة الأصناف مرة واحدة عند تحميل الصفحة
$(document).ready(function() {
    $.get('/api/items', function(data) {
        window.itemsList = data;
    });
});