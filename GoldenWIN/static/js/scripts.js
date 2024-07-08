 var cardStates = {};
    
    var socket = io();
    socket.on('connect', function() {
        console.log('Conectado ao servidor');
    });
    
    socket.on('disconnect', function() {
        console.log('Desconectado do servidor');
    });
    
    socket.on('console_output', function(data) {
        var consoleDiv = document.getElementById('console_' + data.script);
        if (consoleDiv) {
            consoleDiv.innerHTML += data.output + '<br>';
            consoleDiv.scrollTop = consoleDiv.scrollHeight;
        }
    });
    
    function createMiniCard(row) {
    var result = formatResult(row.result || 'Pendente');
    var resultClass = getResultClass(row.result || 'Pendente');
    var cardId = `card-details-${row.id}`;
    var displayStyle = cardStates[row.id] ? "block" : "none";
    var miniCardHtml = `
    <div class="mini-card" onclick="toggleCardDetails(${row.id})">
    <strong>${formatTime(row.time)} ${row.symbol} ${row.direction} ${row.timeframe}</strong><br>
    <span class="${resultClass}">${result}</span>
    <div id="${cardId}" class="card-details" style="display:${displayStyle};">
        <p>Payout: ${row.payout}</p>
        <p>Open: ${row.open}</p>
        <p>Close: ${row.close}</p>
        <p>Open🐔: ${row.open_g1} </p>
        <p>Close🐔: ${row.close_g1}</p>
        <p>Open🐔🐔: ${row.open_g2}</p>
        <p>Close🐔🐔: ${row.close_g2}</p>
        <p>Volume: ${row.volume}</p>
        <p>Volatilidade: ${row.volatility}</p>
    </div>
    </div>
    `;
    return miniCardHtml;
    
    }
    
    
    
    function toggleCardDetails(id) {
    var detailsDiv = document.getElementById(`card-details-${id}`);
    if (detailsDiv.style.display === "none") {
    detailsDiv.style.display = "block";
    cardStates[id] = true;
    } else {
    detailsDiv.style.display = "none";
    cardStates[id] = false;
    }
    }
    // Lista para armazenar os dados dos ativos
    var assetsData = [];
    
    function filterAssets() {
    var input = document.getElementById('searchInput').value.toLowerCase();
    var filteredData = assetsData.filter(row => row.symbol.toLowerCase().includes(input));
    displaySuggestions(filteredData);
    updateMiniCards(filteredData);
    }
    
    function displaySuggestions(filteredData) {
    var suggestionsDiv = document.getElementById('suggestions');
    suggestionsDiv.innerHTML = '';  // Limpa sugestões anteriores
    
    // Usar um Set para evitar ativos duplicados
    var uniqueAssets = new Set();
    filteredData.slice(0, 5).forEach(row => {
    uniqueAssets.add(row.symbol);
    });
    
    // Adicionar itens de sugestão únicos
    uniqueAssets.forEach(symbol => {
    var suggestionItem = document.createElement('a');
    suggestionItem.href = "#";
    suggestionItem.className = "list-group-item list-group-item-action";
    suggestionItem.innerText = symbol;
    suggestionItem.onclick = function() {
        document.getElementById('searchInput').value = symbol;
        updateMiniCards([filteredData.find(row => row.symbol === symbol)]);
        suggestionsDiv.innerHTML = '';
    };
    suggestionsDiv.appendChild(suggestionItem);
    });
    }
    
    
    function updateMiniCards(filteredData) {
    var miniCardsContainer = document.getElementById('mini_cards_container');
    miniCardsContainer.innerHTML = '';
    filteredData.forEach(row => {
    miniCardsContainer.innerHTML += createMiniCard(row);
    });
    }
    
    
    
    
    
    function fetchSignals() {
    fetch('/update_table')
    .then(response => response.json())
    .then(data => {
        assetsData = data;
    
        // Atualizar sinais pendentes
        var pendingSignalsDiv = document.getElementById('pending_signals');
        var pendingHtml = '';
        var pricePromises = [];
    
        data.forEach(row => {
            if (row.sent !== '' && row.result === '') {
                var emoji = row.direction === 'CALL' ? '🟢' : '🔴';
                var signalClass = row.direction === 'CALL' ? "last-signal" : "last-signal";
                var chickenEmojis = '';
    
                if (row.open && row.close && !row.result && !row.open_g1 && !row.close_g1) {
                    chickenEmojis = 'Resultado Parcial🐔: ';
                } else if (row.open_g1 && row.close_g1 && !row.result && !row.open_g2 && !row.close_g2) {
                    chickenEmojis = 'Resultado Parcial🐔🐔: ';
                } else if (!row.open && !row.close && !row.result && !row.open_g1 && !row.close_g1) {
                    chickenEmojis = 'Resultado Parcial: ';
                }
    
    
    // Adiciona a promise para buscar o preço atual e o preço de abertura do símbolo
    var pricePromise = fetch('/get_prices', {
    method: 'POST',
    headers: {
    'Content-Type': 'application/json'
    },
    body: JSON.stringify({
    symbol: row.symbol,
    timeframe: row.timeframe,
    time_str: row.time
    })
    })
    .then(response => response.json())
    .then(priceData => {
    if (!priceData.error) {
    var winningStatus = '';
    
    if (priceData.open_price === 0) {
        winningStatus = '';
    } else if (priceData.current_price === priceData.open_price) {
        winningStatus = 'Doji ☑️';
    } else if (row.direction === 'CALL') {
        winningStatus = priceData.current_price > priceData.open_price ? 'Win ✅' : 'Loss ❌';
    } else if (row.direction === 'PUT') {
        winningStatus = priceData.current_price < priceData.open_price ? 'Win ✅' : 'Loss ❌';
    }
    return {
        symbol: row.symbol,
        now_price: priceData.current_price,
        open_price: priceData.open_price,
        html: `
            <div class="alert alert-success ${signalClass} position-relative" role="alert">
                <strong>${emoji} ${row.symbol} ${emoji}</strong><br>
                Horário: ${formatTime(row.time)}<br>
                Expiração da Vela: ${row.timeframe}<br>
                Direção: ${row.direction}<br>
                ${chickenEmojis}
                ${winningStatus}<br>
                ${priceData.open_price} / ${priceData.current_price}<br>
            </div>`
    };
    } else {
    return {
        symbol: row.symbol,
        now_price: 0,
        open_price: 0,
        html: `
            <div class="alert alert-success ${signalClass} position-relative" role="alert">
                <strong>${emoji} ${row.symbol} ${emoji}</strong><br>
                Horário: ${formatTime(row.time)}<br>
                Expiração da Vela: ${row.timeframe}<br>
                Direção: ${row.direction}<br>
                ${chickenEmojis}
            </div>`
    };
    }
    });
                pricePromises.push(pricePromise);
            }
        });
    
        Promise.all(pricePromises).then(results => {
            results.forEach(result => {
                pendingHtml += result.html;
            });
    
            if (pendingHtml === '') {
                pendingHtml = '<p>Nenhum sinal pendente.</p>';
            }
            pendingSignalsDiv.innerHTML = pendingHtml;
        });

    // Atualizar o último sinal enviado
    var lastSignalDiv = document.getElementById('last_signal');
    if (data.length > 0) {
    var lastRow = data.find(row => row.sent !== '' && row.result === '');
    if (lastRow) {
    var emoji = lastRow.direction === 'CALL' ? '🟢' : '🔴';
    lastSignalDiv.innerHTML = `<strong>${emoji} Último Sinal Enviado</strong><br>`;
    lastSignalDiv.innerHTML += `Ativo: ${lastRow.symbol}<br>`;
    lastSignalDiv.innerHTML += `Horário: ${formatTime(lastRow.time)}<br>`;
    lastSignalDiv.innerHTML += `Expiração da Vela: ${lastRow.timeframe}<br>`;
    lastSignalDiv.innerHTML += `Direção: ${lastRow.direction}<br>`;
    
    // Função para verificar se é dispositivo móvel
    function isMobileDevice() {
        return window.innerWidth < 768; // Ponto de corte típico para dispositivos móveis
    }
    
       // Montagem do link de acordo com o tipo de dispositivo
       var iqOptionLink, quotexLink;
    if (isMobileDevice()) {
        // Link para abrir o aplicativo da IQ Option no dispositivo móvel (deve ser configurado corretamente)
        quotexLink = 'https://qxbroker.com/pt/trade';
        iqOptionLink = 'iqoption://'; // Esquema de URI para abrir o app da IQ Option
    } else {
        // Link para abrir o site da IQ Option no computador
        quotexLink = 'https://qxbroker.com/pt/trade';
        iqOptionLink = 'https://iqoption.com/traderoom';
    }
    
    
    // Adiciona o link com o ícone ao HTML do último sinal
    lastSignalDiv.innerHTML += `Payout: ${lastRow.payout}<br>`;
    lastSignalDiv.innerHTML += `<a href="${iqOptionLink}" target="_blank"><img src="icons/iqoption.png" alt="IQ Option" style="width:50px;height:50px;vertical-align:middle;"></a>`
    lastSignalDiv.innerHTML += `<a href="${quotexLink}" target="_blank"><img src="icons/quotex.png" alt="IQ Option" style="width:50px;height:50px;vertical-align:middle;"></a><br>`;
    
    
                    } else {
                        lastSignalDiv.innerHTML = '<p>Nenhum sinal enviado ainda.</p>';
                    }
                } else {
                    lastSignalDiv.innerHTML = '<p>Nenhum sinal enviado ainda.</p>';
                }
    
                // Atualizar os últimos 5 sinais com resultados
                var last5SignalsDiv = document.getElementById('last_5_signals');
                var last5Html = '';
                var filteredData = data.filter(row => row.result !== '').sort((a, b) => b.id - a.id).slice(0, 5);
                filteredData.forEach(row => {
                    var resultClass = getResultClass(row.result);
                    last5Html += `<div class="mini-card"><strong>${formatTime(row.time)} ${row.symbol} ${row.direction} ${row.timeframe}</strong><br> - <span class="${resultClass}">${formatResult(row.result)}</span></div>`;
                });
                last5SignalsDiv.innerHTML = last5Html;
    
                // Atualizar mini cards na aba analítico
                var miniCardsContainer = document.getElementById('mini_cards_container');
                var miniCardsHtml = '';
                data.forEach(row => {
                    miniCardsHtml += createMiniCard(row);
                });
                miniCardsContainer.innerHTML = miniCardsHtml;
    
                // Atualizar Resultados do Dia
                var dailyResultsDiv = document.getElementById('daily_results');
                var today = new Date();
                today.setHours(0, 0, 0, 0);  // Meia-noite de hoje
    
                var dailyData = data.filter(row => new Date(row.time) >= today && row.result !== '');
                var total = dailyData.length;
                var winCount = dailyData.filter(row => row.result === 'WIN ✅').length;
                var winChickenCount = dailyData.filter(row => row.result === 'WIN ✅🐔').length;
                var winDoubleChickenCount = dailyData.filter(row => row.result === 'WIN ✅🐔🐔').length;
                var losscount = dailyData.filter(row => row.result === 'LOSS ❌').length;
    
                var winPercentage = (total > 0) ? ((winCount / total) * 100).toFixed(2) : 0;
                var winChickenPercentage = (total > 0) ? (((winChickenCount + winCount) / total) * 100).toFixed(2) : 0;
                var winDoubleChickenPercentage = (total > 0) ? (((winDoubleChickenCount + winChickenCount + winCount) / total) * 100).toFixed(2) : 0;
                
                var dailyHtml = `<p>Total de Sinais: ${total}</p>`;
                dailyHtml += `<p>WIN ✅: ${winCount} (${winPercentage}%)</p>`;
                dailyHtml += `<p>WIN ✅🐔: ${winChickenCount} (${winChickenPercentage}%)</p>`;
                dailyHtml += `<p>WIN ✅🐔🐔: ${winDoubleChickenCount} (${winDoubleChickenPercentage}%)</p>`;
                dailyHtml += `<p>LOSS ❌: ${losscount}</p>`;
    
    
    
                dailyResultsDiv.innerHTML = dailyHtml;
    
            })
            .catch(error => {
                console.error('Erro ao atualizar a tabela de sinais:', error);
            });
    }
    
    setInterval(fetchSignals, 1000);  // Ajuste o intervalo de atualização conforme necessário
    
    function updateClock() {
        var now = new Date();
        var hours = now.getHours().toString().padStart(2, '0');
        var minutes = now.getMinutes().toString().padStart(2, '0');
        var seconds = now.getSeconds().toString().padStart(2, '0');
        document.getElementById('clock').textContent = hours + ':' + minutes + ':' + seconds;
    }
    
    function formatTime(dateTimeStr) {
        var date = new Date(dateTimeStr);
        var hours = date.getHours().toString().padStart(2, '0');
        var minutes = date.getMinutes().toString().padStart(2, '0');
        return hours + ':' + minutes;
    }
    
    function formatResult(result) {
        if (result === 'WIN') {
            return 'WIN ✅';
        } else if (result === 'WIN 🐔') {
            return 'WIN ✅🐔';
        } else if (result === 'WIN 🐔🐔') {
            return 'WIN ✅🐔🐔';
        } else {
            return result;
        }
    }
    
    function getResultClass(result) {
        if (result.includes('WIN')) {
            return 'text-success';
        } else if (result.includes('LOSS')) {
            return 'text-danger';
        } else {
            return 'text-warning';
        }
    }
    
    setInterval(updateClock, 1000);
    
    function logout() {
    // Realiza a ação de logoff (pode ser um redirecionamento ou uma chamada AJAX)
    // Aqui está um exemplo simples de redirecionamento
    window.location.href = '/logout';
    }

    function confirmLogout(event) {
    event.preventDefault();  // Evita a navegação padrão
    
    if (confirm("Você tem certeza que deseja fazer logout?")) {
        window.location.href = "/logout";  // Redireciona para a rota de logout
    }
    }
  
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js')
            .then(function(registration) {
                console.log('Service Worker registrado com sucesso:', registration.scope);
            })
            .catch(function(error) {
                console.log('Falha ao registrar o Service Worker:', error);
            });
    }
   
    var scriptStates = {
    'ia.py': false,
    'telegrambot.py': false,
    'candles.py': false,
    'candles_iq.py': false
    };
    
    function toggleScript(script) {
    var button = document.getElementById('button_' + script);
    var consoleDiv = document.getElementById('console_' + script);
    
    if (scriptStates[script]) {
    stopScript(script).then(() => {
        button.innerHTML = 'Iniciar ' + getScriptName(script);
        if (consoleDiv) {
            consoleDiv.innerHTML += 'Script ' + getScriptName(script) + ' parado.<br>';
        }
        scriptStates[script] = false;
    }).catch(() => {
        if (consoleDiv) {
            consoleDiv.innerHTML += 'Erro ao parar o script ' + getScriptName(script) + '.<br>';
        }
    });
    } else {
    startScript(script).then(() => {
        button.innerHTML = 'Parar ' + getScriptName(script);
        if (consoleDiv) {
            consoleDiv.innerHTML += 'Script ' + getScriptName(script) + ' em execução.<br>';
        }
        scriptStates[script] = true;
    }).catch(() => {
        if (consoleDiv) {
            consoleDiv.innerHTML += 'Erro ao iniciar o script ' + getScriptName(script) + '.<br>';
        }
    });
    }
    }
    
    function getScriptName(script) {
    switch (script) {
    case 'ia.py':
        return 'IA';
    case 'telegrambot.py':
        return 'Telegram';
    case 'candles.py':
        return 'MT5';
    case 'candles_iq.py':
        return 'OTC';
    default:
        return '';
    }
    }
    
    function startScript(script) {
    return new Promise((resolve, reject) => {
    fetch(`/start/${script}`, { method: 'GET' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'started') {
                console.log(`Script ${script} iniciado com sucesso`);
                resolve();
            } else {
                console.error(`Erro ao iniciar script ${script}: ${data.message}`);
                reject();
            }
        })
        .catch(error => {
            console.error(`Erro ao iniciar script ${script}: ${error}`);
            reject();
        });
    });
    }
    
    function stopScript(script) {
    return new Promise((resolve, reject) => {
    fetch(`/stop/${script}`, { method: 'GET' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'stopped') {
                console.log(`Script ${script} parado com sucesso`);
                resolve();
            } else {
                console.error(`Erro ao parar script ${script}: ${data.message}`);
                reject();
            }
        })
        .catch(error => {
            console.error(`Erro ao parar script ${script}: ${error}`);
            reject();
        });
    });
    }
    
    function updateScriptState(script) {
    return new Promise((resolve, reject) => {
    fetch(`/status/${script}`, { method: 'GET' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'running') {
                scriptStates[script] = true;
                var button = document.getElementById('button_' + script);
                if (button) {
                    button.innerHTML = 'Parar ' + getScriptName(script);
                }
                resolve();
            } else {
                scriptStates[script] = false;
                var button = document.getElementById('button_' + script);
                if (button) {
                    button.innerHTML = 'Iniciar ' + getScriptName(script);
                }
                resolve();
            }
        })
        .catch(error => {
            console.error(`Erro ao obter status do script ${script}: ${error}`);
            reject();
        });
    });
    }
    
    window.onload = function() {
    updateScriptState('ia.py');
    updateScriptState('telegrambot.py');
    updateScriptState('candles.py');
    updateScriptState('candles_iq.py');
    };
    
    // Atualizar estados dos scripts ao carregar a página
    document.addEventListener('DOMContentLoaded', () => {
    Object.keys(scriptStates).forEach(script => {
    updateScriptState(script);
    });
    });
    
    // Exemplo de uso do socket para atualizações do console
    var socket = io();
    socket.on('connect', function() {
    console.log('Conectado ao servidor');
    });
    
    socket.on('disconnect', function() {
    console.log('Desconectado do servidor');
    });
    
    socket.on('console_output', function(data) {
    var consoleDiv = document.getElementById('console_' + data.script);
    if (consoleDiv) {
    consoleDiv.innerHTML += data.output + '<br>';
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
    }
    });
    
    // Conectar ao servidor Socket.IO
    var socket = io();
    
    // Ouvinte de eventos para cada script
    socket.on('console_output_IA', function(data) {
    updateConsole('console_ia.py', data.output);
    });
    
    socket.on('console_output_Telegram', function(data) {
    updateConsole('console_telegrambot.py', data.output);
    });
    
    socket.on('console_output_Candles_MT5', function(data) {
    updateConsole('console_candles.py', data.output);
    });
    
    socket.on('console_output_Candles_OTC', function(data) {
    updateConsole('console_candles_iq.py', data.output);
    });
    
    // Função para atualizar a div do console com nova saída
    function updateConsole(consoleId, output) {
    const consoleDiv = document.getElementById(consoleId);
    consoleDiv.innerHTML += output + '<br>'; // Adiciona nova saída
    // Role para o final do console (opcional)
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
    }
    
    // Verifica se o dispositivo é um celular ou tablet (baseado na largura da tela)
    function isMobileDevice() {
    return (typeof window.orientation !== "undefined") || (navigator.userAgent.indexOf('IEMobile') !== -1);
    }
    
    // Adiciona o link correto baseado no tipo de dispositivo
    function addIQOptionLink() {
    var lastSignalDiv = document.getElementById('lastSignalDiv');
    
    if (isMobileDevice()) {
    // Se for dispositivo móvel, adiciona o link para abrir o aplicativo da IQ Option
    lastSignalDiv.innerHTML += '<p>Payout IQ Option: <a href="iqoption://" target="_blank">Abrir IQ Option App</a></p>';
    } else {
    // Se for computador, mantém o link para o site da IQ Option
    lastSignalDiv.innerHTML += '<p>Payout IQ Option: <a href="https://iqoption.com/traderoom" target="_blank">https://iqoption.com/traderoom</a></p>';
    }
    }
    
    // Chama a função para adicionar o link correto quando a página carrega
    window.onload = addIQOptionLink;
   
    function toggleFlag(checkbox) {
    var flagId = checkbox.id.replace('_toggle', '');
    var isActive = checkbox.checked;
    console.log(flagId + " is " + (isActive ? "activated" : "deactivated"));
    // Adicione a lógica adicional que você precisar aqui
    }
   
    document.addEventListener('DOMContentLoaded', function() {
    fetch('/events')
        .then(response => response.json())
        .then(data => {
            const eventsContainer = document.getElementById('events-container');
            eventsContainer.innerHTML = '';  // Clear any existing content
    
            data.forEach(event => {
                const eventBox = document.createElement('div');
                eventBox.className = 'event-box';
    
                eventBox.innerHTML = `
                    <strong>Título:</strong> ${event.title}<br>
                    <strong>Hora:</strong> ${event.datetime}<br>
                    <strong>País:</strong> ${event.country}<br>
                    <strong>Impacto:</strong> ${event.impact}
                `;
    
                eventsContainer.appendChild(eventBox);
            });
        })
        .catch(error => console.error('Error fetching events:', error));
    });

    function toggleSidebar() {
    const sidebar = document.getElementById("mySidebar");
    if (sidebar.style.left === "-250px") {
        sidebar.style.left = "0";
    } else {
        sidebar.style.left = "-250px";
    }
    }
    
    document.addEventListener("DOMContentLoaded", function() {
    // Selecionar a seção "Home" ao carregar a página
    const homeLink = document.querySelector('[data-target="#sintetico"]');
    if (homeLink) {
    homeLink.click(); // Simular um clique no link da seção "Home"
    }
    });
    
    function selectSection(event) {
    event.preventDefault();
    document.querySelectorAll('.content-section').forEach(section => {
    section.classList.remove('active');
    });
    const target = event.target.getAttribute('data-target');
    document.querySelector(target).classList.add('active');
    closeSidebar();
    }
    
    
    
    function confirmLogout(event) {
    event.preventDefault();
    if (confirm('Você realmente quer sair?')) {
        window.location.href = '/logout';
    }
    }
  
    function loadLogs(scriptName, logId, fromPosition) {
    fetch('/get_logs/' + scriptName + '?from=' + fromPosition)
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            var logDiv = document.getElementById(logId);
            data.logs.forEach(log => {
                logDiv.innerHTML += log + '<br>';
            });
            logDiv.scrollTop = logDiv.scrollHeight; // Move o scroll para o final após carregar os logs
            // Armazena a nova posição para a próxima chamada
            logDiv.dataset.position = data.new_position;
        }
    });
    }
    
    // Carregar logs ao carregar a página com a posição inicial 0
    loadLogs('ia.py', 'ia_logs', 0);
    loadLogs('telegrambot.py', 'telegram_logs', 0);
    loadLogs('candles.py', 'candles_mt5_logs', 0);
    loadLogs('candles_iq.py', 'candles_iq_logs', 0);
    
    // Atualizar logs a cada segundo
    setInterval(() => {
    loadLogs('ia.py', 'ia_logs', document.getElementById('ia_logs').dataset.position || 0);
    loadLogs('telegrambot.py', 'telegram_logs', document.getElementById('telegram_logs').dataset.position || 0);
    loadLogs('candles.py', 'candles_mt5_logs', document.getElementById('candles_mt5_logs').dataset.position || 0);
    loadLogs('candles_iq.py', 'candles_iq_logs', document.getElementById('candles_iq_logs').dataset.position || 0);
    }, 10000);
    
    const publicVapidKey = 'BN31yZx0Hsd0zinaxTp0HNOM2fpqQLg9ThIduUgTDtW7fq0aZjUOvJK2jTg1uxMlGMn5uscVENHL79KufzI8wAI=';
    
    // Função para converter URL safe base64
    function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
    }
    
    if ('serviceWorker' in navigator && 'PushManager' in window) {
    navigator.serviceWorker.ready.then(function(registration) {
    return registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
    });
    }).then(function(subscription) {
    fetch('/subscribe', {
        method: 'POST',
        body: JSON.stringify(subscription),
        headers: {
            'Content-Type': 'application/json'
        }
    });
    });
    }
    
    // Função para formatar a data para o formato americano (YYYY-MM-DD)
    function formatDateToAmerican(date) {
    const [day, month, year] = date.split('/');
    return `${year}-${month}-${day}`;
    }
    
    // Função para formatar a data para o formato brasileiro (DD/MM/YYYY)
    function formatDateToBrazilian(date) {
    const [year, month, day] = date.split('-');
    return `${day}/${month}/${year}`;
    }
    
    // Função para tratar o envio do formulário
    function handleFormSubmit(event) {
    const dateInput = document.getElementById('data_pagamento');
    const formattedDate = formatDateToAmerican(dateInput.value);
    dateInput.value = formattedDate;
    }
    
    // Função para adicionar automaticamente barras à data
    function formatInputDate(event) {
    const input = event.target;
    const value = input.value.replace(/\D/g, '');
    let formattedValue = '';
    
    if (value.length > 2) {
        formattedValue += value.slice(0, 2) + '/';
    }
    if (value.length > 4) {
        formattedValue += value.slice(2, 4) + '/';
    }
    formattedValue += value.slice(4, 8);
    
    input.value = formattedValue;
    }
    
    // Função para definir a data atual no formato brasileiro
    function setCurrentDate() {
    const today = new Date();
    const day = String(today.getDate()).padStart(2, '0');
    const month = String(today.getMonth() + 1).padStart(2, '0'); // Janeiro é 0
    const year = today.getFullYear();
    const currentDate = `${day}/${month}/${year}`;
    document.getElementById('data_pagamento').value = currentDate;
    }
    
    // Definir a data atual ao carregar a página
    window.onload = setCurrentDate;
   
    document.getElementById('addLicenseForm').addEventListener('submit', async function(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    const response = await fetch(form.action, {
        method: form.method,
        body: formData
    });
    
    const message = await response.text();
    alert(message);
    });
 
    function openTab(tabName) {
    // Esconder todos os conteúdos de abas
    var tabContents = document.getElementsByClassName("tab-content");
    for (var i = 0; i < tabContents.length; i++) {
        tabContents[i].classList.remove("active");
    }
    
    // Mostrar apenas o conteúdo da aba selecionada
    document.getElementById(tabName).classList.add("active");
    }
    $(document).ready(function() {
    $('#createUserForm').submit(function(event) {
        var newPassword = $('#new_password').val();
        var confirmPassword = $('#confirm_password').val();
    
        if (newPassword !== confirmPassword) {
            alert('As senhas não coincidem. Por favor, digite novamente.');
            event.preventDefault(); // Impede o envio do formulário se as senhas não coincidirem
        }
    });
    });