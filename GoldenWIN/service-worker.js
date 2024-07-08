self.addEventListener('install', function(event) {
    console.log('Service Worker instalado');
});

self.addEventListener('activate', function(event) {
    console.log('Service Worker ativado');
});

self.addEventListener('fetch', function(event) {
    console.log('Interceptando fetch para:', event.request.url);
});

self.addEventListener('push', function(event) {
    console.log('Push recebido');
    var data = event.data ? event.data.json() : { title: 'Sem título', body: 'Sem mensagem' };
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/icons/icon-192x192.png'
        })
    );
});
