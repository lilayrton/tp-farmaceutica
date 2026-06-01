// FarmaShield Dashboard - Logic & API Integrations

document.addEventListener('DOMContentLoaded', () => {
    // ----------------------------------------------------
    // Tab Navigation
    // ----------------------------------------------------
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');

    const tabHeaders = {
        'tab-panel': {
            title: 'Panel de Farmacovigilancia',
            subtitle: 'Consolidado operativo en tiempo real de múltiples bases de datos.'
        },
        'tab-verify': {
            title: 'Verificador de Receta (OP-2)',
            subtitle: 'Detección de interacciones graves en Neo4j, alertas en Redis y efectos adversos en MongoDB.'
        },
        'tab-trace': {
            title: 'Trazabilidad y Frío (OP-3)',
            subtitle: 'Consulta lineal del lote en MongoDB y stream de lecturas del sensor térmico en Redis.'
        },
        'tab-interactions': {
            title: 'Análisis de Principios Activos (OP-4)',
            subtitle: 'Predicción de interacciones en el grafo de Neo4j para medicamentos nuevos o cargados.'
        },
        'tab-close-alert': {
            title: 'Resolución de Alertas (OP-5)',
            subtitle: 'Emisión de dictamen médico para cerrar alertas de Redis y propagar información.'
        }
    };

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');
            
            // Toggle active menu item
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // Toggle active content section
            tabContents.forEach(content => content.classList.remove('active'));
            document.getElementById(targetTab).classList.add('active');

            // Update Header Text
            if (tabHeaders[targetTab]) {
                pageTitle.textContent = tabHeaders[targetTab].title;
                pageSubtitle.textContent = tabHeaders[targetTab].subtitle;
            }

            // If switching to panel, reload data automatically
            if (targetTab === 'tab-panel') {
                loadPanelData();
            }
        });
    });

    // Toggle Neo4j Subgroup on Alert Form based on choice
    const closeResultadoSelect = document.getElementById('close-resultado');
    const neo4jGroup = document.getElementById('neo4j-interaction-group');
    if (closeResultadoSelect && neo4jGroup) {
        closeResultadoSelect.addEventListener('change', (e) => {
            if (e.target.value === 'confirmado') {
                neo4jGroup.classList.remove('hidden');
            } else {
                neo4jGroup.classList.add('hidden');
            }
        });
    }

    // ----------------------------------------------------
    // API Fetchers
    // ----------------------------------------------------
    const API_BASE = window.location.origin;

    // Refresh Panel Button
    const btnRefresh = document.getElementById('btn-refresh-panel');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            btnRefresh.classList.add('spinning');
            loadPanelData().finally(() => {
                setTimeout(() => btnRefresh.classList.remove('spinning'), 600);
            });
        });
    }

    // Load OP-1 Panel
    async function loadPanelData() {
        const statusMongo = document.getElementById('status-mongo');
        const statusNeo4j = document.getElementById('status-neo4j');
        const statusRedis = document.getElementById('status-redis');

        try {
            const response = await fetch(`${API_BASE}/panel`);
            const data = await response.json();

            // Set DB indicator status
            if (data.errores) {
                if (data.errores.mongodb) setStatus(statusMongo, false); else setStatus(statusMongo, true);
                if (data.errores.neo4j) setStatus(statusNeo4j, false); else setStatus(statusNeo4j, true);
                if (data.errores.redis) setStatus(statusRedis, false); else setStatus(statusRedis, true);
            } else {
                setStatus(statusMongo, true);
                setStatus(statusNeo4j, true);
                setStatus(statusRedis, true);
            }

            // Update Metric Values
            document.getElementById('val-redis-cola').textContent = data.redis.reportes_pendientes_evaluacion ?? 0;
            document.getElementById('val-redis-alertas').textContent = data.redis.top_alertas_activas ? data.redis.top_alertas_activas.length : 0;

            // Render active alerts (Redis ZSET)
            const alertsList = document.getElementById('redis-alertas-list');
            alertsList.innerHTML = '';
            if (data.redis.top_alertas_activas && data.redis.top_alertas_activas.length > 0) {
                data.redis.top_alertas_activas.forEach(alert => {
                    const tr = document.createElement('tr');
                    
                    let sevClass = 'text-green';
                    if (alert.severidad >= 4) sevClass = 'text-red font-bold';
                    else if (alert.severidad >= 3) sevClass = 'text-orange';

                    // Quick prefill trigger
                    const alertId = alert.alerta_id || alert.id;
                    const actionBtn = `<button class="btn-quick-close" onclick="prefillCloseAlert('${alertId}', '${alert.medicamento_id}')" title="Resolver alerta"><i class="fa-solid fa-check-double text-purple"></i> Resolver</button>`;

                    tr.innerHTML = `
                        <td class="font-mono">${alertId}</td>
                        <td class="font-mono">${alert.medicamento_id}</td>
                        <td><span class="${sevClass}"><i class="fa-solid fa-triangle-exclamation"></i> Nivel ${alert.severidad}</span></td>
                        <td><span class="badge ${alert.severidad >= 4 ? 'badge-red' : 'badge-orange'}">${alert.tipo}</span></td>
                        <td>${alert.descripcion} ${actionBtn}</td>
                    `;
                    alertsList.appendChild(tr);
                });
            } else {
                alertsList.innerHTML = '<tr><td colspan="5" class="text-center text-green"><i class="fa-solid fa-circle-check"></i> No hay alertas activas en el sistema.</td></tr>';
            }

            // Render Hot Counters (Redis String)
            const countersList = document.getElementById('redis-counters-list');
            countersList.innerHTML = '';
            const hotMeds = data.redis.medicamentos_con_contador_elevado_24h || {};
            const hotMedKeys = Object.keys(hotMeds);
            if (hotMedKeys.length > 0) {
                hotMedKeys.forEach(med => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div>
                            <span class="title text-red">${med}</span>
                            <div class="subtitle">Clave: contadores:${med}</div>
                        </div>
                        <span class="badge badge-red">${hotMeds[med]} reportes (24h)</span>
                    `;
                    countersList.appendChild(li);
                });
            } else {
                countersList.innerHTML = '<li class="text-muted text-center"><i class="fa-solid fa-square-check text-green"></i> Tráfico operativo normal (sin excesos).</li>';
            }

            // Render MongoDB aggregate
            const mongoList = document.getElementById('mongo-reported-list');
            mongoList.innerHTML = '';
            const reportedMonth = data.mongodb.medicamentos_mas_reportados_ultimo_mes || [];
            if (reportedMonth.length > 0) {
                reportedMonth.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${item.medicamento || 'Medicamento Desconocido'}</strong></td>
                        <td class="font-mono">${item.medicamento_id}</td>
                        <td><span class="text-orange font-bold">${item.total_reportes} reportes</span></td>
                    `;
                    mongoList.appendChild(tr);
                });
            } else {
                mongoList.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Sin reportes en el último mes.</td></tr>';
            }

            // Render Neo4j dangerous principles
            const neo4jList = document.getElementById('neo4j-dangerous-list');
            neo4jList.innerHTML = '';
            const dangerousPA = data.neo4j.principios_activos_mas_peligrosos || [];
            if (dangerousPA.length > 0) {
                dangerousPA.forEach(item => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div>
                            <span class="title text-purple">${item.principio_activo}</span>
                            <div class="subtitle">${item.familia || 'Sin familia química'}</div>
                        </div>
                        <span class="badge badge-purple">${item.total_interacciones_peligrosas} cruces graves</span>
                    `;
                    neo4jList.appendChild(li);
                });
            } else {
                neo4jList.innerHTML = '<li class="text-muted text-center">Sin interacciones de riesgo.</li>';
            }

        } catch (error) {
            console.error('Error loading panel data:', error);
            setStatus(statusMongo, false);
            setStatus(statusNeo4j, false);
            setStatus(statusRedis, false);
        }
    }

    function setStatus(element, isConnected) {
        if (!element) return;
        if (isConnected) {
            element.classList.remove('disconnected');
            element.classList.add('connected');
        } else {
            element.classList.remove('connected');
            element.classList.add('disconnected');
        }
    }

    // Initial Load
    loadPanelData();

    // ----------------------------------------------------
    // OP-2: Prescription Verification Form
    // ----------------------------------------------------
    const formVerify = document.getElementById('form-verify-prescription');
    const verifyCard = document.getElementById('verify-result-card');
    const verifyHeader = document.getElementById('verify-result-header');
    const verifyBody = document.getElementById('verify-result-body');

    if (formVerify) {
        formVerify.addEventListener('submit', async (e) => {
            e.preventDefault();
            const paciente = document.getElementById('verify-paciente').value.trim();
            const medicamento = document.getElementById('verify-medicamento').value.trim();

            verifyCard.classList.remove('hidden');
            verifyBody.innerHTML = '<div class="text-center"><i class="fa-solid fa-spinner fa-spin text-primary" style="font-size: 2rem;"></i><p class="text-muted mt-2">Analizando interacciones de fármacos (Neo4j), alertas de lotes (Redis) e historial médico (MongoDB)...</p></div>';

            try {
                const response = await fetch(`${API_BASE}/prescripcion/verificar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paciente_id: paciente, medicamento_id: medicamento })
                });
                const result = await response.json();

                // Check errors
                if (result.errores && Object.keys(result.errores).length > 0) {
                    verifyCard.className = 'grid-card result-card danger-border';
                    verifyHeader.innerHTML = `<h2><i class="fa-solid fa-circle-exclamation text-red"></i> Error en la Operación</h2>`;
                    verifyBody.innerHTML = `<pre class="font-mono text-red" style="white-space: pre-wrap;">${JSON.stringify(result.errores, null, 2)}</pre>`;
                    return;
                }

                // Render result based on high_risk flag
                if (result.riesgo_alto) {
                    verifyCard.className = 'grid-card result-card danger-border';
                    verifyHeader.innerHTML = `<h2><i class="fa-solid fa-circle-xmark text-red"></i> PRESCRIPCIÓN RECHAZADA - RIESGO DETECTADO</h2>`;
                } else {
                    verifyCard.className = 'grid-card result-card success-border';
                    verifyHeader.innerHTML = `<h2><i class="fa-solid fa-circle-check text-green"></i> PRESCRIPCIÓN AUTORIZADA - SIN RIESGOS DETECTADOS</h2>`;
                }

                let html = `
                    <div style="display: flex; flex-direction: column; gap: 1.5rem;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border-color);">
                            <div>
                                <span class="text-muted text-sm">ID Paciente:</span>
                                <p class="font-mono" style="font-size: 1.1rem;"><strong>${result.paciente_id}</strong></p>
                            </div>
                            <div>
                                <span class="text-muted text-sm">ID Medicamento:</span>
                                <p class="font-mono" style="font-size: 1.1rem;"><strong>${result.medicamento_id}</strong></p>
                            </div>
                        </div>
                `;

                // 1. Graph Interactions (Neo4j)
                const conflicts = result.neo4j.interacciones_detectadas || [];
                html += `
                    <div>
                        <h3><i class="fa-solid fa-circle-nodes text-purple"></i> Interacciones en Grafo Paciente (Neo4j)</h3>
                `;
                if (conflicts.length > 0) {
                    html += `
                        <div class="table-container mt-2">
                            <table class="custom-table">
                                <thead>
                                    <tr>
                                        <th>Principios Activos Involucrados</th>
                                        <th>Severidad</th>
                                        <th>Mecanismo</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;
                    conflicts.forEach(c => {
                        let sevClass = 'badge-green';
                        if (c.severidad === 'contraindicada' || c.severidad === 'grave') sevClass = 'badge-red';
                        else if (c.severidad === 'moderada') sevClass = 'badge-orange';

                        html += `
                            <tr>
                            <td><strong>${c.pa_nuevo || c.principio_1}</strong> <i class="fa-solid fa-arrow-right-arrow-left text-muted"></i> <strong>${c.pa_existente || c.principio_2}</strong></td>    
                            <td><span class="badge ${sevClass}">${c.severidad}</span></td>
                                <td>${c.mecanismo || 'N/D'}</td>
                            </tr>
                        `;
                    });
                    html += `</tbody></table></div>`;
                } else {
                    html += `<p class="text-green mt-1"><i class="fa-solid fa-check"></i> El paciente no está tomando medicamentos que interaccionen negativamente.</p>`;
                }
                html += `</div>`;

                // 2. Active Alerts (Redis)
                const activeAlerts = result.redis.alertas_activas_sobre_medicamento || [];
                html += `
                    <div>
                        <h3><i class="fa-solid fa-bell text-orange"></i> Alertas de Lote Activas (Redis)</h3>
                `;
                if (activeAlerts.length > 0) {
                    html += `
                        <ul class="simple-list mt-2">
                    `;
                    activeAlerts.forEach(a => {
                        const alertId = a.alerta_id || a.id;
                        html += `
                            <li style="border-color: rgba(255, 75, 107, 0.2);">
                                <div>
                                    <span class="title text-red">${alertId} (${a.tipo})</span>
                                    <div class="subtitle">${a.descripcion}</div>
                                </div>
                                <span class="badge badge-red">Nivel ${a.severidad}</span>
                            </li>
                        `;
                    });
                    html += `</ul>`;
                } else {
                    html += `<p class="text-green mt-1"><i class="fa-solid fa-check"></i> No hay alertas sanitarias ni de cadena de frío vigentes para este medicamento.</p>`;
                }
                html += `</div>`;

                // Escalated alert confirmation (Redis)
                if (result.redis.alerta_escalada) {
                    const alertEscId = result.redis.alerta_escalada.alerta_id || result.redis.alerta_escalada.id;
                    html += `
                        <div style="background: rgba(255, 75, 107, 0.05); border: 1px solid rgba(255, 75, 107, 0.2); padding: 1rem; border-radius: 8px;">
                            <h4 class="text-red"><i class="fa-solid fa-shield-virus"></i> Alerta Escalada e Insertada en Cola</h4>
                            <p class="text-muted text-sm mt-1">Debido a una interacción farmacológica grave detectada, se ha publicado automáticamente la alerta <strong class="font-mono text-primary">${alertEscId}</strong> en Redis para evaluación urgente.</p>
                        </div>
                    `;
                }

                // 3. Adverse Effects History (MongoDB)
                const aeHistory = result.mongodb.historial_efectos_adversos_recientes || [];
                html += `
                    <div>
                        <h3><i class="fa-solid fa-file-medical-flag text-blue"></i> Historial Reciente de Efectos Adversos (MongoDB)</h3>
                `;
                if (aeHistory.length > 0) {
                    html += `
                        <div class="table-container mt-2">
                            <table class="custom-table">
                                <thead>
                                    <tr>
                                        <th>Efecto Adverso (MedDRA)</th>
                                        <th>Gravedad</th>
                                        <th>País de Reporte</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;
                    aeHistory.forEach(ae => {
                        let gravClass = 'text-green';
                        if (ae.gravedad === 'grave') gravClass = 'text-red font-bold';
                        else if (ae.gravedad === 'moderada') gravClass = 'text-orange';

                        html += `
                            <tr>
                                <td><strong>${ae.efecto}</strong></td>
                                <td><span class="${gravClass}">${ae.gravedad}</span></td>
                                <td>${ae.pais}</td>
                            </tr>
                        `;
                    });
                    html += `</tbody></table></div>`;
                } else {
                    html += `<p class="text-green mt-1"><i class="fa-solid fa-check"></i> Sin registros de efectos adversos para este medicamento en los últimos 6 meses.</p>`;
                }
                html += `</div>`;

                html += `</div>`; // Close column layout
                verifyBody.innerHTML = html;

            } catch (err) {
                console.error(err);
                verifyCard.className = 'grid-card result-card danger-border';
                verifyHeader.innerHTML = `<h2><i class="fa-solid fa-circle-exclamation text-red"></i> Error</h2>`;
                verifyBody.innerHTML = `<p class="text-red">Error al intentar verificar la prescripción. Asegúrate de que la API esté activa.</p>`;
            }
        });
    }

    // ----------------------------------------------------
    // OP-3: Trace Lote and Cold Chain Form
    // ----------------------------------------------------
    const formTrace = document.getElementById('form-trace-lote');
    const traceCard = document.getElementById('trace-result-card');
    const traceBody = document.getElementById('trace-result-body');

    if (formTrace) {
        formTrace.addEventListener('submit', async (e) => {
            e.preventDefault();
            const loteNum = document.getElementById('trace-lote-num').value.trim();
            const vehiculo = document.getElementById('trace-vehiculo').value.trim();

            traceCard.classList.remove('hidden');
            traceBody.innerHTML = '<div class="text-center"><i class="fa-solid fa-spinner fa-spin text-primary" style="font-size: 2rem;"></i><p class="text-muted mt-2">Consultando trazas históricas en MongoDB y Stream térmico en Redis...</p></div>';

            try {
                const response = await fetch(`${API_BASE}/lote/${loteNum}/trazabilidad?vehiculo_id=${vehiculo}`);
                const result = await response.json();

                // Check errors
                if (result.errores && Object.keys(result.errores).length > 0) {
                    traceBody.innerHTML = `<pre class="font-mono text-red" style="white-space: pre-wrap;">${JSON.stringify(result.errores, null, 2)}</pre>`;
                    return;
                }

                const redisInfo = result.redis || {};
                const mongoInfo = result.mongodb || {};

                let html = `<div style="display: flex; flex-direction: column; gap: 1.5rem;">`;

                // 1. Cold Chain (Redis Stream)
                const hasRupture = redisInfo.ruptura_detectada;
                let ruptureBanner = '';
                if (hasRupture) {
                    ruptureBanner = `
                        <div style="background: rgba(255, 75, 107, 0.08); border: 1px solid var(--red); padding: 1.25rem; border-radius: 12px; margin-bottom: 1.5rem;">
                            <h4 class="text-red"><i class="fa-solid fa-biohazard"></i> Ruptura de Cadena de Frío Detectada</h4>
                            <p class="text-primary mt-1"><strong>Vehículo:</strong> ${redisInfo.vehiculo_id} | ${redisInfo.mensaje}</p>
                            ${redisInfo.alerta_publicada ? `<p class="text-muted text-sm mt-1">Se ha generado una alerta automática con ID: <strong class="font-mono text-purple">${redisInfo.alerta_publicada.alerta_id}</strong></p>` : ''}
                        </div>
                    `;
                } else {
                    ruptureBanner = `
                        <div style="background: rgba(0, 229, 117, 0.08); border: 1px solid var(--green); padding: 1.25rem; border-radius: 12px; margin-bottom: 1.5rem;">
                            <h4 class="text-green"><i class="fa-solid fa-snowflake"></i> Cadena de Frío Estable</h4>
                            <p class="text-primary mt-1"><strong>Vehículo:</strong> ${redisInfo.vehiculo_id} | Las temperaturas se mantuvieron en el rango reglamentario (2-8°C).</p>
                        </div>
                    `;
                }

                html += ruptureBanner;

                // Render Temperature Stream dots
                const temps = redisInfo.tendencia_ultimas_12_lecturas || [];
                html += `
                    <div>
                        <h3><i class="fa-solid fa-chart-area text-blue"></i> Historial del Sensor de Temperatura <span class="badge badge-blue">Redis Stream</span></h3>
                        <p class="text-muted text-sm">Últimas lecturas del vehículo:</p>
                        <div class="temp-stream-container">
                `;
                if (temps.length > 0) {
                    temps.forEach(t => {
                        const tempVal = parseFloat(t.temperatura);
                        const isNormal = tempVal >= 2 && tempVal <= 8;
                        html += `
                            <span class="temp-dot ${isNormal ? 'normal' : 'critical'}" title="Vehículo: ${t.vehiculo_id}">
                                ${tempVal.toFixed(1)}°C
                            </span>
                        `;
                    });
                } else {
                    html += `<p class="text-muted">No hay registros de temperatura para este vehículo en Redis.</p>`;
                }
                html += `</div></div>`;

                // 2. Trazabilidad MongoDB
                html += `
                    <div style="border-top: 1px solid var(--border-color); padding-top: 1.5rem;">
                        <h3><i class="fa-solid fa-route text-purple"></i> Trazabilidad del Lote <span class="badge badge-purple">MongoDB Document</span></h3>
                `;

                if (mongoInfo.error) {
                    html += `<p class="text-red mt-2"><i class="fa-solid fa-circle-exclamation"></i> Lote no encontrado en la base de datos histórica de MongoDB.</p>`;
                } else {
                    html += `
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; padding: 1rem; background: rgba(255,255,255,0.01); border-radius: 8px; border: 1px solid var(--border-color);">
                            <div>
                                <span class="text-muted text-sm">Lote Nro:</span>
                                <p class="font-mono"><strong>${mongoInfo.numero_lote}</strong></p>
                            </div>
                            <div>
                                <span class="text-muted text-sm">Medicamento ID:</span>
                                <p class="font-mono"><strong>${mongoInfo.medicamento_id?.$oid || mongoInfo.medicamento_id}</strong></p>
                            </div>
                            <div>
                                <span class="text-muted text-sm">Fecha Fabricación:</span>
                                <p>${mongoInfo.fecha_fabricacion ? new Date(mongoInfo.fecha_fabricacion.$date || mongoInfo.fecha_fabricacion).toLocaleDateString() : 'N/D'}</p>
                            </div>
                            <div>
                                <span class="text-muted text-sm">Fecha Vencimiento:</span>
                                <p class="text-orange"><strong>${mongoInfo.fecha_vencimiento ? new Date(mongoInfo.fecha_vencimiento.$date || mongoInfo.fecha_vencimiento).toLocaleDateString() : 'N/D'}</strong></p>
                            </div>
                        </div>

                        <div class="trace-timeline">
                    `;

                    // Manufacture Node
                    html += `
                        <div class="trace-node origin">
                            <div class="trace-node-title">Planta de Manufactura: ${mongoInfo.planta_origen || 'N/D'}</div>
                            <div class="trace-node-desc">Fabricado por el laboratorio creador del medicamento.</div>
                        </div>
                    `;

                    // Distributors Nodes
                    const dist = mongoInfo.distribucion || [];
                    if (dist.length > 0) {
                        dist.forEach(d => {
                            html += `
                                <div class="trace-node">
                                    <div class="trace-node-title">Distribuidor: ${d.distribuidor_id}</div>
                                    <div class="trace-node-desc">
                                        Fecha despacho: ${new Date(d.fecha_despacho.$date || d.fecha_despacho).toLocaleDateString()}<br>
                                        Estado: <span class="text-blue">Entregado</span>
                                    </div>
                                </div>
                            `;
                        });
                    }

                    // Current Custody Node
                    html += `
                        <div class="trace-node current">
                            <div class="trace-node-title">Custodia Actual: ${mongoInfo.custodia_actual?.entidad || 'Farmacia / Almacén'}</div>
                            <div class="trace-node-desc">
                                Dirección: ${mongoInfo.custodia_actual?.ubicacion || 'En Tránsito'}<br>
                                Estado de Stock: <span class="text-green font-bold">Disponible</span>
                            </div>
                        </div>
                    `;

                    html += `</div>`; // Close timeline
                }

                html += `</div></div>`; // Close column layout
                traceBody.innerHTML = html;

            } catch (err) {
                console.error(err);
                traceBody.innerHTML = `<p class="text-red">Error al consultar trazabilidad. Asegúrate de que la API esté activa.</p>`;
            }
        });
    }

    // ----------------------------------------------------
    // OP-4: Analyze Interactions Form
    // ----------------------------------------------------
    const formInt = document.getElementById('form-analyze-interactions');
    const intCard = document.getElementById('interactions-result-card');
    const intBody = document.getElementById('interactions-result-body');

    if (formInt) {
        formInt.addEventListener('submit', async (e) => {
            e.preventDefault();
            const medId = document.getElementById('interaction-med-id').value.trim() || 'nuevo';
            const customPa = document.getElementById('interaction-custom-pa').value.trim();

            intCard.classList.remove('hidden');
            intBody.innerHTML = '<div class="text-center"><i class="fa-solid fa-spinner fa-spin text-primary" style="font-size: 2rem;"></i><p class="text-muted mt-2">Mapeando principios activos en MongoDB y prediciendo interacciones en Neo4j...</p></div>';

            try {
                // Build query params
                let url = `${API_BASE}/medicamento/${medId}/interacciones`;
                if (customPa) {
                    const paArray = customPa.split(',').map(item => item.trim()).filter(item => item !== '');
                    const queryParams = paArray.map(pa => `principios_activos=${encodeURIComponent(pa)}`).join('&');
                    url += `?${queryParams}`;
                }

                const response = await fetch(url);
                const result = await response.json();

                // Check errors
                if (result.errores && Object.keys(result.errores).length > 0) {
                    intBody.innerHTML = `<pre class="font-mono text-red" style="white-space: pre-wrap;">${JSON.stringify(result.errores, null, 2)}</pre>`;
                    return;
                }

                const mongoData = result.mongodb || {};
                const neo4jData = result.neo4j || {};

                let html = `<div style="display: flex; flex-direction: column; gap: 1.5rem;">`;

                // Medicine Info Box
                html += `
                    <div style="background: rgba(255,255,255,0.01); border: 1px solid var(--border-color); padding: 1.25rem; border-radius: 12px;">
                        <h4 class="text-blue"><i class="fa-solid fa-prescription-bottle"></i> Información del Fármaco Registrado</h4>
                        <p class="mt-2"><strong>Nombre Comercial:</strong> ${mongoData.nombre_comercial || 'Medicamento en Desarrollo'}</p>
                        <p><strong>Nombre Genérico:</strong> ${mongoData.nombre_generico || 'N/D'}</p>
                        <p class="mt-2 text-purple"><strong>Principios Activos Encontrados:</strong> ${(neo4jData.principios_activos_analizados || []).join(', ')}</p>
                    </div>
                `;

                // Interacciones Mapeadas
                html += `
                    <div>
                        <h3><i class="fa-solid fa-triangle-exclamation text-orange"></i> Interacciones de Grafo Encontradas <span class="badge badge-orange">Neo4j Cypher</span></h3>
                `;

                if (neo4jData.error) {
                    html += `<p class="text-red mt-2">${neo4jData.error}</p>`;
                } else {
                    const ints = neo4jData.interacciones_detectadas || [];
                    if (ints.length > 0) {
                        html += `
                            <p class="text-muted text-sm mt-1">Se detectaron ${ints.length} interacciones de riesgo. Se aconseja precaución médica:</p>
                            
                            <!-- Severity Summary Widgets -->
                            <div style="display: flex; gap: 0.5rem; margin: 1rem 0; flex-wrap: wrap;">
                                ${Object.keys(neo4jData.resumen_por_severidad || {}).map(sev => {
                                    const count = neo4jData.resumen_por_severidad[sev];
                                    let cls = 'badge-green';
                                    if (sev === 'contraindicada' || sev === 'grave') cls = 'badge-red';
                                    else if (sev === 'moderada') cls = 'badge-orange';
                                    return count > 0 ? `<span class="badge ${cls}">${sev}: ${count}</span>` : '';
                                }).join('')}
                            </div>

                            <div class="table-container">
                                <table class="custom-table">
                                    <thead>
                                        <tr>
                                            <th>Primer Fármaco</th>
                                            <th></th>
                                            <th>Segundo Fármaco</th>
                                            <th>Severidad</th>
                                            <th>Mecanismo de Acción</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        `;
                        
                        ints.forEach(i => {
                            let sevCls = 'badge-green';
                            if (i.severidad === 'contraindicada' || i.severidad === 'grave') sevCls = 'badge-red';
                            else if (i.severidad === 'moderada') sevCls = 'badge-orange';

                            html += `
                                <tr>
                                    <td><strong>${i.principio_activo_1}</strong> <span class="text-muted">(${i.med_1_nombre || 'N/D'})</span></td>
                                    <td><i class="fa-solid fa-ban text-red"></i></td>
                                    <td><strong>${i.principio_activo_2}</strong> <span class="text-muted">(${i.med_2_nombre || 'N/D'})</span></td>
                                    <td><span class="badge ${sevCls}">${i.severidad}</span></td>
                                    <td>${i.mecanismo || 'Sin mecanismo documentado.'}</td>
                                </tr>
                            `;
                        });

                        html += `</tbody></table></div>`;
                    } else {
                        html += `<p class="text-green mt-2"><i class="fa-solid fa-circle-check"></i> Sin interacciones riesgosas conocidas en el grafo para estos principios activos.</p>`;
                    }
                }

                html += `</div></div>`;
                intBody.innerHTML = html;

            } catch (err) {
                console.error(err);
                intBody.innerHTML = `<p class="text-red">Error al predecir interacciones. Asegúrate de que la API esté activa.</p>`;
            }
        });
    }

    // ----------------------------------------------------
    // OP-5: Close Alert Form
    // ----------------------------------------------------
    const formClose = document.getElementById('form-close-alert');
    const closeCard = document.getElementById('close-result-card');
    const closeBody = document.getElementById('close-result-body');

    if (formClose) {
        formClose.addEventListener('submit', async (e) => {
            e.preventDefault();

            const alertId = document.getElementById('close-alerta-id').value.trim();
            const medId = document.getElementById('close-med-id').value.trim();
            const investigador = document.getElementById('close-investigador').value.trim();
            const resultado = document.getElementById('close-resultado').value;
            const acciones = document.getElementById('close-acciones').value.trim();

            // Check if new interaction needs to be added
            let nuevaInteraccion = null;
            if (resultado === 'confirmado') {
                const pa1 = document.getElementById('new-pa1').value.trim();
                const pa2 = document.getElementById('new-pa2').value.trim();
                const tipo = document.getElementById('new-tipo').value.trim();
                const severidad = document.getElementById('new-severidad').value;
                const mecanismo = document.getElementById('new-mecanismo').value.trim();

                if (pa1 && pa2) {
                    nuevaInteraccion = {
                        pa1,
                        pa2,
                        tipo: tipo || 'farmacocinetica',
                        severidad: severidad || 'grave',
                        mecanismo: mecanismo
                    };
                }
            }

            closeCard.classList.remove('hidden');
            closeBody.innerHTML = '<div class="text-center"><i class="fa-solid fa-spinner fa-spin text-purple" style="font-size: 2rem;"></i><p class="text-muted mt-2">Removiendo de Redis, registrando dictamen en MongoDB y actualizando Neo4j...</p></div>';

            try {
                const payload = {
                    alerta_id: alertId,
                    medicamento_id: medId,
                    resultado,
                    investigador_id: investigador,
                    acciones_tomadas: acciones,
                    nueva_interaccion: nuevaInteraccion
                };

                const response = await fetch(`${API_BASE}/alerta/cerrar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();

                // Check errors
                if (result.errores && Object.keys(result.errores).length > 0) {
                    closeBody.innerHTML = `<pre class="font-mono text-red" style="white-space: pre-wrap;">${JSON.stringify(result.errores, null, 2)}</pre>`;
                    return;
                }

                // Render result
                let html = `
                    <div style="display: flex; flex-direction: column; gap: 1.25rem;">
                        <div style="background: rgba(0, 229, 117, 0.08); border: 1px solid var(--green); padding: 1rem; border-radius: 8px;">
                            <h4 class="text-green"><i class="fa-solid fa-circle-check"></i> Alerta Cerrada Exitosamente</h4>
                            <p class="text-muted text-sm mt-1">La alerta <strong>${result.alerta_id}</strong> fue removida del panel de control de farmacovigilancia.</p>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;">
                            <div>
                                <span class="text-muted text-sm">Dictamen persistido en MongoDB:</span>
                                <p class="text-green"><strong>${result.mongodb.dictamen_id ? 'OK' : 'Omitido'}</strong></p>
                            </div>
                            <div>
                                <span class="text-muted text-sm">Remoción de Redis:</span>
                                <p>Removida de ZSET: <strong>${result.redis.alerta_consumida ? 'Sí' : 'No'}</strong></p>
                                ${result.redis.contador_decrementado ? `<p class="text-orange text-sm">Contador 24h decrementado. Actual: <strong>${result.redis.contador_actual}</strong></p>` : ''}
                            </div>
                        </div>
                `;

                // Neo4j update info
                const neoResult = result.neo4j || {};
                html += `
                    <div>
                        <h3><i class="fa-solid fa-circle-nodes text-purple"></i> Actualización del Grafo de Interacciones (Neo4j)</h3>
                `;
                if (neoResult.accion === 'omitido') {
                    html += `<p class="text-muted mt-1"><i class="fa-solid fa-circle-info"></i> ${neoResult.motivo}</p>`;
                } else if (neoResult.error) {
                    html += `<p class="text-red mt-1"><i class="fa-solid fa-circle-xmark"></i> ${neoResult.error}</p>`;
                } else {
                    html += `
                        <div class="table-container mt-2">
                            <table class="custom-table">
                                <thead>
                                    <tr>
                                        <th>Relación Guardada</th>
                                        <th>Tipo</th>
                                        <th>Severidad</th>
                                        <th>Mecanismo</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td><strong>${neoResult.pa1}</strong> <i class="fa-solid fa-ban text-red"></i> <strong>${neoResult.pa2}</strong></td>
                                        <td>${neoResult.tipo}</td>
                                        <td><span class="badge badge-red">${neoResult.severidad}</span></td>
                                        <td>${neoResult.mecanismo || 'N/D'}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    `;
                }
                html += `</div></div>`;
                closeBody.innerHTML = html;

                // Reload the main panel to reflect changes
                loadPanelData();

            } catch (err) {
                console.error(err);
                closeBody.innerHTML = `<p class="text-red">Error al intentar cerrar la alerta. Verifica la conexión con la API.</p>`;
            }
        });
    }

    // ----------------------------------------------------
    // Custom Autocomplete Dropdown (replaces browser default datalist)
    // ----------------------------------------------------
    const inputsWithSuggestions = document.querySelectorAll('input[data-list]');
    
    inputsWithSuggestions.forEach(input => {
        const datalistId = input.getAttribute('data-list');
        const datalist = document.getElementById(datalistId);
        if (!datalist) return;
        
        const options = Array.from(datalist.querySelectorAll('option')).map(opt => ({
            value: opt.value,
            text: opt.textContent || ''
        }));
        
        let dropdown = null;
        
        function showSuggestions(filterText = '') {
            closeSuggestions();
            
            const filtered = options.filter(opt => 
                opt.value.toLowerCase().includes(filterText.toLowerCase()) ||
                opt.text.toLowerCase().includes(filterText.toLowerCase())
            );
            
            if (filtered.length === 0) return;
            
            dropdown = document.createElement('div');
            dropdown.className = 'custom-autocomplete-dropdown';
            
            dropdown.style.width = `${input.offsetWidth}px`;
            dropdown.style.top = `${input.offsetTop + input.offsetHeight}px`;
            dropdown.style.left = `${input.offsetLeft}px`;
            
            filtered.forEach(opt => {
                const item = document.createElement('div');
                item.className = 'custom-autocomplete-item';
                
                const valSpan = document.createElement('span');
                valSpan.className = 'item-value';
                valSpan.textContent = opt.value;
                item.appendChild(valSpan);
                
                if (opt.text) {
                    const descSpan = document.createElement('span');
                    descSpan.className = 'item-desc';
                    descSpan.textContent = opt.text;
                    item.appendChild(descSpan);
                }
                
                item.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    input.value = opt.value;
                    input.dispatchEvent(new Event('input'));
                    closeSuggestions();
                });
                
                dropdown.appendChild(item);
            });
            
            input.parentNode.appendChild(dropdown);
        }
        
        function closeSuggestions() {
            if (dropdown) {
                dropdown.remove();
                dropdown = null;
            }
        }
        
        input.addEventListener('focus', () => {
            showSuggestions(input.value);
        });
        
        input.addEventListener('input', () => {
            showSuggestions(input.value);
        });
        
        input.addEventListener('blur', () => {
            setTimeout(closeSuggestions, 150);
        });
    });
});

// ----------------------------------------------------
// Global Helper Functions (Accessible from inline HTML)
// ----------------------------------------------------
window.prefillCloseAlert = function(alertaId, medicamentoId) {
    // Switch to Close Alert Tab
    const tabBtn = document.querySelector('.nav-item[data-tab="tab-close-alert"]');
    if (tabBtn) {
        tabBtn.click();
    }

    // Populate Fields
    document.getElementById('close-alerta-id').value = alertaId;
    document.getElementById('close-med-id').value = medicamentoId;
    document.getElementById('close-resultado').focus();
};
