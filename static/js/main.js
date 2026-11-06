/**
 * CineMatch AI - Luxury Cinematic Platform Controller
 * Features:
 * - Live TMDB Search Autocomplete with Poster Thumbnails
 * - Horizontal Carousel Scrolling
 * - Real-Time Multi-Filter Movie Discovery Engine
 * - Cinematic Backdrop Details Modal
 * - AJAX Watchlist Management
 */

document.addEventListener('DOMContentLoaded', () => {
    initGlobalSearch();
    initCarouselControls();
    initExploreFilters();
    initMovieDetailModals();
    initWatchlistButtons();
    initSimilarMovieFeature();
});

// ==========================================================================
// 1. GLOBAL LIVE SEARCH WITH POSTER THUMBNAILS
// ==========================================================================
function initGlobalSearch() {
    const searchInputs = [
        { input: document.getElementById('globalMovieSearch'), dropdown: document.getElementById('heroSearchDropdown'), form: document.getElementById('heroSearchForm') },
        { input: document.getElementById('movieSearchInput'), dropdown: document.getElementById('searchDropdown'), form: document.getElementById('movieSearchForm') }
    ];

    searchInputs.forEach(({ input, dropdown, form }) => {
        if (!input || !dropdown) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            clearTimeout(debounceTimer);

            if (query.length < 1) {
                dropdown.style.display = 'none';
                dropdown.innerHTML = '';
                return;
            }

            debounceTimer = setTimeout(() => {
                fetch(`/api/search-tmdb?q=${encodeURIComponent(query)}`)
                    .then(res => res.json())
                    .then(data => {
                        dropdown.innerHTML = '';
                        if (!data || data.length === 0) {
                            dropdown.innerHTML = '<div class="p-3 text-secondary fs-xs text-center font-outfit">No matching films found in TMDB catalog</div>';
                            dropdown.style.display = 'block';
                            return;
                        }

                        data.forEach(item => {
                            const row = document.createElement('a');
                            row.className = 'search-suggestion-row';
                            row.href = `/recommend?movie=${encodeURIComponent(item.title)}&movie_id=${item.id}`;
                            
                            const posterHtml = item.poster_url 
                                ? `<img src="${item.poster_url}" alt="${escapeHtml(item.title)}" class="suggestion-thumb" onerror="this.src=''; this.style.display='none';">`
                                : `<div class="suggestion-thumb d-flex align-items-center justify-content-center bg-dark"><i class="fa-solid fa-film text-cyan fs-xs"></i></div>`;

                            row.innerHTML = `
                                ${posterHtml}
                                <div class="flex-grow-1 text-truncate">
                                    <div class="suggestion-title text-truncate">${escapeHtml(item.title)}</div>
                                    <div class="text-secondary fs-2xs text-truncate">${escapeHtml(item.genres_str || '')}</div>
                                </div>
                                <div class="text-end text-nowrap">
                                    <span class="badge bg-secondary-subtle text-light fs-2xs me-1">${item.release_year || 'N/A'}</span>
                                    <span class="badge bg-dark-subtle text-cyan fs-2xs">${item.language_name || 'EN'}</span>
                                    <div class="text-warning fs-2xs mt-1"><i class="fa-solid fa-star me-1"></i>${item.vote_average ? item.vote_average.toFixed(1) : '0.0'}</div>
                                </div>
                            `;

                            row.addEventListener('click', (ev) => {
                                ev.preventDefault();
                                input.value = item.title;
                                dropdown.style.display = 'none';
                                window.location.href = `/recommend?movie=${encodeURIComponent(item.title)}&movie_id=${item.id}`;
                            });

                            dropdown.appendChild(row);
                        });
                        dropdown.style.display = 'block';
                    })
                    .catch(err => console.error('Search autocomplete error:', err));
            }, 250);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    });
}

// ==========================================================================
// 2. HORIZONTAL CAROUSEL CONTROLS
// ==========================================================================
function initCarouselControls() {
    document.querySelectorAll('.btn-carousel-nav').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-target');
            const track = document.getElementById(targetId);
            if (!track) return;

            const isNext = this.classList.contains('btn-next');
            const scrollDistance = track.clientWidth * 0.75;
            track.scrollBy({
                left: isNext ? scrollDistance : -scrollDistance,
                behavior: 'smooth'
            });
        });
    });
}

// ==========================================================================
// 3. EXPLORE MOVIES REAL-TIME FILTER ENGINE
// ==========================================================================
function initExploreFilters() {
    const filterForm = document.getElementById('filterForm');
    const grid = document.getElementById('exploreMovieGrid');
    const loading = document.getElementById('exploreLoading');
    const emptyState = document.getElementById('exploreEmptyState');
    const countBadge = document.getElementById('currentResultsCount');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    const currPageNum = document.getElementById('currentPageNum');
    const totalPagesNum = document.getElementById('totalPagesNum');
    const clearAllBtn = document.getElementById('clearAllFiltersBtn');
    const clearGenresBtn = document.getElementById('clearGenresBtn');
    const resetEmptyBtn = document.getElementById('resetEmptyBtn');

    if (!filterForm || !grid) return;

    let currentPage = 1;

    function fetchFilteredMovies(page = 1) {
        currentPage = page;
        grid.style.opacity = '0.3';
        if (loading) loading.classList.remove('d-none');
        if (emptyState) emptyState.classList.add('d-none');

        const lang = document.getElementById('filterLanguage').value;
        const ind = document.getElementById('filterIndustry').value;
        const period = document.getElementById('filterPeriod').value;
        const sort = document.getElementById('filterSort').value;

        // Checked genres
        const checkedGenres = [];
        document.querySelectorAll('.genre-checkbox:checked').forEach(cb => {
            checkedGenres.push(cb.value);
        });

        const params = new URLSearchParams({
            language: lang,
            industry: ind,
            genres: checkedGenres.join(','),
            period: period,
            sort_by: sort,
            page: currentPage
        });

        fetch(`/api/discover?${params.toString()}`)
            .then(res => res.json())
            .then(data => {
                grid.style.opacity = '1';
                if (loading) loading.classList.add('d-none');

                if (!data.success || !data.movies || data.movies.length === 0) {
                    grid.innerHTML = '';
                    if (emptyState) emptyState.classList.remove('d-none');
                    if (countBadge) countBadge.textContent = '0';
                    if (prevBtn) prevBtn.disabled = true;
                    if (nextBtn) nextBtn.disabled = true;
                    return;
                }

                // Update pagination
                if (countBadge) countBadge.textContent = data.total_results.toLocaleString();
                if (currPageNum) currPageNum.textContent = data.page;
                if (totalPagesNum) totalPagesNum.textContent = data.total_pages;
                if (prevBtn) prevBtn.disabled = data.page <= 1;
                if (nextBtn) nextBtn.disabled = data.page >= data.total_pages;

                // Render movie cards
                grid.innerHTML = '';
                data.movies.forEach(movie => {
                    const card = createMovieCardElement(movie);
                    grid.appendChild(card);
                });

                // Re-bind click handlers
                initMovieDetailModals();
                initWatchlistButtons();
            })
            .catch(err => {
                grid.style.opacity = '1';
                if (loading) loading.classList.add('d-none');
                console.error('Filter fetch error:', err);
            });
    }

    // Trigger on change of dropdowns
    ['filterLanguage', 'filterIndustry', 'filterPeriod', 'filterSort'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => fetchFilteredMovies(1));
    });

    // Trigger on genre checkboxes
    document.querySelectorAll('.genre-checkbox').forEach(cb => {
        cb.addEventListener('change', () => fetchFilteredMovies(1));
    });

    // Pagination
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) fetchFilteredMovies(currentPage - 1);
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            fetchFilteredMovies(currentPage + 1);
        });
    }

    // Clear filters
    function resetAll() {
        document.getElementById('filterLanguage').value = '';
        document.getElementById('filterIndustry').value = '';
        document.getElementById('filterPeriod').value = '';
        document.getElementById('filterSort').value = 'popularity.desc';
        document.querySelectorAll('.genre-checkbox').forEach(cb => cb.checked = false);
        fetchFilteredMovies(1);
    }

    if (clearAllBtn) clearAllBtn.addEventListener('click', resetAll);
    if (resetEmptyBtn) resetEmptyBtn.addEventListener('click', resetAll);
    if (clearGenresBtn) {
        clearGenresBtn.addEventListener('click', () => {
            document.querySelectorAll('.genre-checkbox').forEach(cb => cb.checked = false);
            fetchFilteredMovies(1);
        });
    }
}

function createMovieCardElement(movie) {
    const card = document.createElement('div');
    card.className = 'movie-poster-card';
    card.setAttribute('data-movie-id', movie.id);

    const isAdded = movie.in_watchlist;
    const posterImg = movie.poster_url 
        ? `<img src="${movie.poster_url}" alt="${escapeHtml(movie.title)}" class="poster-img" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.classList.remove('d-none');">`
        : '';

    card.innerHTML = `
        <div class="poster-media position-relative">
            <div class="card-rating-badge">
                <i class="fa-solid fa-star text-warning me-1"></i>
                <span>${movie.vote_average.toFixed(1)}</span>
            </div>
            ${posterImg}
            <div class="poster-svg-fallback ${movie.poster_url ? 'd-none' : ''}">
                <i class="fa-solid fa-film text-cyan fs-1 mb-2 opacity-50"></i>
                <span class="fs-xs fw-bold text-white text-center px-2">${escapeHtml(movie.title)}</span>
            </div>
            <div class="poster-hover-overlay">
                <div class="overlay-actions d-flex flex-column gap-2 p-3 w-100">
                    <button type="button" class="btn btn-cyan btn-sm rounded-pill w-100 btn-movie-details" data-movie-id="${movie.id}">
                        <i class="fa-solid fa-circle-info me-1"></i> Details
                    </button>
                    <button type="button" class="btn ${isAdded ? 'btn-success' : 'btn-outline-light'} btn-sm rounded-pill w-100 btn-watchlist-toggle" 
                            data-movie-id="${movie.id}" 
                            data-is-added="${isAdded ? 'true' : 'false'}">
                        <i class="${isAdded ? 'fa-solid' : 'fa-regular'} fa-bookmark me-1"></i> 
                        ${isAdded ? 'Saved' : 'Watchlist'}
                    </button>
                    <button type="button" class="btn btn-outline-cyan btn-sm rounded-pill w-100 btn-movie-similar" 
                            data-movie-id="${movie.id}" 
                            data-movie-title="${escapeHtml(movie.title)}">
                        <i class="fa-solid fa-wand-magic-sparkles me-1"></i> Similar
                    </button>
                </div>
            </div>
        </div>
        <div class="poster-info pt-2 px-1">
            <h6 class="poster-title font-outfit text-white text-truncate mb-1" title="${escapeHtml(movie.title)}">${escapeHtml(movie.title)}</h6>
            <div class="d-flex align-items-center justify-content-between text-secondary fs-2xs mb-1">
                <span>${movie.release_year || 'N/A'}</span>
                <span class="badge bg-dark-subtle text-cyan fs-2xs">${escapeHtml(movie.language_name || movie.language_code || 'EN')}</span>
            </div>
            <div class="text-secondary fs-2xs text-truncate">${escapeHtml(movie.genres_str || '')}</div>
        </div>
    `;
    return card;
}

// ==========================================================================
// 4. MOVIE DETAILS MODAL (CINEMATIC BACKDROP & FULL METADATA)
// ==========================================================================
function openMovieDetailsModal(movieId) {
    if (!movieId) return;
    const modalEl = document.getElementById('movieDetailModal');
    if (!modalEl) return;
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);

    fetch(`/api/movie-details/${movieId}`)
        .then(res => res.json())
        .then(data => {
            if (!data.success || !data.movie) return;
            const m = data.movie;

            // Backdrop image
            const backdropImg = document.getElementById('modalBackdropImg');
            if (backdropImg) {
                backdropImg.src = m.backdrop_url || m.poster_url || '';
                backdropImg.style.display = (m.backdrop_url || m.poster_url) ? 'block' : 'none';
            }

            // Poster image
            const posterImg = document.getElementById('modalPosterImg');
            const posterFallback = document.getElementById('modalPosterFallback');
            if (posterImg) {
                if (m.poster_url) {
                    posterImg.src = m.poster_url;
                    posterImg.style.display = 'block';
                    if (posterFallback) posterFallback.classList.add('d-none');
                } else {
                    posterImg.style.display = 'none';
                    if (posterFallback) {
                        posterFallback.classList.remove('d-none');
                        document.getElementById('modalFallbackTitle').textContent = m.title;
                    }
                }
            }

            document.getElementById('modalMovieTitle').textContent = m.title;
            document.getElementById('modalMovieOriginalTitle').textContent = (m.original_title && m.original_title !== m.title) ? `Original: ${m.original_title}` : '';
            document.getElementById('modalMovieRating').textContent = m.vote_average ? Number(m.vote_average).toFixed(1) : '0.0';
            document.getElementById('modalMovieVotes').textContent = `(${m.vote_count || 0} votes)`;
            document.getElementById('modalMovieYear').textContent = m.release_year || 'N/A';
            document.getElementById('modalMovieRuntime').textContent = `${m.runtime || 120} min`;
            document.getElementById('modalMovieLanguage').textContent = m.language_name || (m.language_code ? m.language_code.toUpperCase() : 'English');
            document.getElementById('modalMovieDirector').textContent = m.director || 'Unknown';
            document.getElementById('modalMovieCast').textContent = m.cast_str || (Array.isArray(m.cast) ? m.cast.join(', ') : 'Not listed');
            document.getElementById('modalMovieOverview').textContent = m.overview || 'No overview available.';

            // Genre badges
            const genresContainer = document.getElementById('modalMovieGenresChips');
            if (genresContainer) {
                genresContainer.innerHTML = '';
                const genreList = Array.isArray(m.genres) ? m.genres : (m.genres_str ? m.genres_str.split(',') : []);
                genreList.forEach(g => {
                    const badge = document.createElement('span');
                    badge.className = 'badge bg-cyan-subtle text-cyan fs-2xs px-2 py-1 rounded-pill';
                    badge.textContent = g.trim();
                    genresContainer.appendChild(badge);
                });
            }

            // Modal action buttons
            const modalWatchlistBtn = document.getElementById('modalWatchlistBtn');
            if (modalWatchlistBtn) {
                modalWatchlistBtn.setAttribute('data-movie-id', m.id);
                modalWatchlistBtn.setAttribute('data-poster-path', m.poster_path || '');
            }

            const modalRecommendBtn = document.getElementById('modalRecommendBtn');
            if (modalRecommendBtn) {
                modalRecommendBtn.setAttribute('data-movie-id', m.id);
                modalRecommendBtn.setAttribute('data-movie-title', m.title);
            }

            modal.show();
        })
        .catch(err => console.error('Details fetch error:', err));
}

function initMovieDetailModals() {
    // Event delegation on document so dynamically rendered cards work automatically
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.btn-movie-details');
        if (btn) {
            e.preventDefault();
            const movieId = btn.getAttribute('data-movie-id');
            if (movieId) openMovieDetailsModal(movieId);
        }
    });
}

// ==========================================================================
// 5. AJAX WATCHLIST TOGGLE
// ==========================================================================
function toggleWatchlistAction(btn) {
    const movieId = btn.getAttribute('data-movie-id');
    const isAdded = btn.getAttribute('data-is-added') === 'true';
    const posterPath = btn.getAttribute('data-poster-path') || '';

    if (!movieId) return;

    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    btn.disabled = true;

    const endpoint = isAdded ? `/watchlist/remove/${movieId}` : '/watchlist/add';
    const method = isAdded ? 'DELETE' : 'POST';

    fetch(endpoint, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie_id: parseInt(movieId), poster_path: posterPath })
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        if (data.success) {
            const newAddedState = !isAdded;
            btn.setAttribute('data-is-added', newAddedState ? 'true' : 'false');

            if (newAddedState) {
                btn.className = btn.classList.contains('btn-watchlist-modal') 
                    ? 'btn btn-success rounded-pill px-4 btn-watchlist-modal'
                    : 'btn btn-success btn-sm rounded-pill w-100 btn-watchlist-toggle';
                btn.innerHTML = '<i class="fa-solid fa-bookmark me-1"></i> Saved';
            } else {
                btn.className = btn.classList.contains('btn-watchlist-modal')
                    ? 'btn btn-outline-cyan rounded-pill px-4 btn-watchlist-modal'
                    : 'btn btn-outline-light btn-sm rounded-pill w-100 btn-watchlist-toggle';
                btn.innerHTML = '<i class="fa-regular fa-bookmark me-1"></i> Watchlist';
            }

            // Sync any matching card on the page
            document.querySelectorAll(`.btn-watchlist-toggle[data-movie-id="${movieId}"]`).forEach(cardBtn => {
                cardBtn.setAttribute('data-is-added', newAddedState ? 'true' : 'false');
                cardBtn.className = newAddedState 
                    ? 'btn btn-success btn-sm rounded-pill w-100 btn-watchlist-toggle'
                    : 'btn btn-outline-light btn-sm rounded-pill w-100 btn-watchlist-toggle';
                cardBtn.innerHTML = newAddedState 
                    ? '<i class="fa-solid fa-bookmark me-1"></i> Saved' 
                    : '<i class="fa-regular fa-bookmark me-1"></i> Watchlist';
            });
        } else {
            btn.innerHTML = originalHtml;
            alert(data.message || 'Action failed.');
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
        console.error('Watchlist error:', err);
    });
}

function initWatchlistButtons() {
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.btn-watchlist-toggle, .btn-watchlist-modal');
        if (btn) {
            e.preventDefault();
            e.stopPropagation();
            toggleWatchlistAction(btn);
        }
    });
}

// ==========================================================================
// 6. SIMILAR MOVIES FEATURE (MACHINE LEARNING & TMDB MODAL)
// ==========================================================================
function initSimilarMovieFeature() {
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.btn-movie-similar');
        if (btn) {
            e.preventDefault();
            const movieId = btn.getAttribute('data-movie-id');
            const movieTitle = btn.getAttribute('data-movie-title') || '';
            openSimilarMoviesModal(movieId, movieTitle, btn);
        }
    });

    const retryBtn = document.getElementById('similarRetryBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            const lastId = retryBtn.getAttribute('data-movie-id');
            const lastTitle = retryBtn.getAttribute('data-movie-title') || '';
            openSimilarMoviesModal(lastId, lastTitle, null);
        });
    }
}

function openSimilarMoviesModal(movieId, movieTitle, triggerBtn) {
    if (!movieId && !movieTitle) return;

    let originalHtml = '';
    if (triggerBtn) {
        originalHtml = triggerBtn.innerHTML;
        triggerBtn.disabled = true;
        triggerBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Finding...';
    }

    // Close Details Modal if open
    const detailModalEl = document.getElementById('movieDetailModal');
    if (detailModalEl) {
        const detailModal = bootstrap.Modal.getInstance(detailModalEl);
        if (detailModal) detailModal.hide();
    }

    // Open Similar Movies Modal
    const modalEl = document.getElementById('similarMoviesModal');
    if (!modalEl) return;
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();

    // Reset View State
    const targetTitleEl = document.getElementById('similarModalTargetTitle');
    if (targetTitleEl) targetTitleEl.textContent = movieTitle || (`Movie #${movieId}`);

    const loadingState = document.getElementById('similarLoadingState');
    const errorState = document.getElementById('similarErrorState');
    const contentState = document.getElementById('similarContentState');

    if (loadingState) loadingState.classList.remove('d-none');
    if (errorState) errorState.classList.add('d-none');
    if (contentState) contentState.classList.add('d-none');

    // Call reliable Flask Similar Endpoint
    const endpoint = `/api/movies/${encodeURIComponent(movieId || 'title')}/similar`;
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            movie_id: movieId,
            title: movieTitle
        })
    })
    .then(res => res.json().then(data => ({ status: res.status, ok: res.ok, data: data })))
    .then(result => {
        const data = result.data;
        if (!data || !data.success || !data.recommendations || data.recommendations.length === 0) {
            showSimilarError(data ? (data.error || 'No similar movies found for this title.') : 'Service unavailable.', movieId, movieTitle);
            return;
        }
        renderSimilarMoviesContent(data);
    })
    .catch(err => {
        console.error('Error fetching similar movies:', err);
        showSimilarError('A connection error occurred while generating recommendations. Please retry.', movieId, movieTitle);
    })
    .finally(() => {
        if (triggerBtn) {
            triggerBtn.disabled = false;
            triggerBtn.innerHTML = originalHtml;
        }
    });
}

function showSimilarError(msg, movieId, movieTitle) {
    const loadingState = document.getElementById('similarLoadingState');
    const errorState = document.getElementById('similarErrorState');
    const contentState = document.getElementById('similarContentState');
    const errorMsgEl = document.getElementById('similarErrorMessage');
    const retryBtn = document.getElementById('similarRetryBtn');

    if (loadingState) loadingState.classList.add('d-none');
    if (contentState) contentState.classList.add('d-none');
    if (errorState) errorState.classList.remove('d-none');
    if (errorMsgEl) errorMsgEl.textContent = msg;

    if (retryBtn) {
        retryBtn.setAttribute('data-movie-id', movieId || '');
        retryBtn.setAttribute('data-movie-title', movieTitle || '');
    }
}

function renderSimilarMoviesContent(data) {
    const loadingState = document.getElementById('similarLoadingState');
    const errorState = document.getElementById('similarErrorState');
    const contentState = document.getElementById('similarContentState');

    if (loadingState) loadingState.classList.add('d-none');
    if (errorState) errorState.classList.add('d-none');
    if (contentState) contentState.classList.remove('d-none');

    const isML = data.source === 'machine_learning';

    // Header updates
    const headingEl = document.getElementById('similarModalTargetTitle');
    const subtitleEl = document.getElementById('similarModalSubtitle');

    if (headingEl) headingEl.textContent = data.selected_movie.title;
    if (subtitleEl) {
        subtitleEl.innerHTML = isML 
            ? `Calculated using TF-IDF feature extraction (5,000 unigrams & bigrams), K-Means clustering (#${data.cluster_used}), and Cosine Similarity`
            : `Curated via TMDB's thematic and keyword similarity graph for live external films`;
    }

    // Selected Movie Anchor Banner
    const sel = data.selected_movie;
    const selPoster = document.getElementById('similarSelectedPoster');
    const selFallback = document.getElementById('similarSelectedFallback');
    const posterSrc = sel.poster_url || (sel.poster_path ? (sel.poster_path.startsWith('http') ? sel.poster_path : 'https://image.tmdb.org/t/p/w300' + sel.poster_path) : '');

    if (selPoster) {
        if (posterSrc) {
            selPoster.src = posterSrc;
            selPoster.style.display = 'block';
            if (selFallback) selFallback.classList.add('d-none');
        } else {
            selPoster.style.display = 'none';
            if (selFallback) selFallback.classList.remove('d-none');
        }
    }

    const selTitle = document.getElementById('similarSelectedTitle');
    if (selTitle) selTitle.textContent = sel.title;

    const selYear = document.getElementById('similarSelectedYear');
    if (selYear) selYear.textContent = sel.release_year || 'N/A';

    const selRating = document.getElementById('similarSelectedRating');
    if (selRating) {
        const ratingVal = sel.vote_average ? Number(sel.vote_average).toFixed(1) : '0.0';
        selRating.innerHTML = `<i class="fa-solid fa-star me-1"></i> ${ratingVal} / 10`;
    }

    const selSource = document.getElementById('similarSelectedSourceBadge');
    if (selSource) {
        if (isML) {
            selSource.className = 'badge bg-cyan-subtle text-cyan fs-2xs px-2 py-1 rounded-pill';
            selSource.innerHTML = `<i class="fa-solid fa-brain me-1"></i> Thematic Cluster #${data.cluster_used}`;
        } else {
            selSource.className = 'badge bg-warning-subtle text-warning fs-2xs px-2 py-1 rounded-pill';
            selSource.innerHTML = `<i class="fa-solid fa-globe me-1"></i> TMDB Similar Movies`;
        }
    }

    const selOverview = document.getElementById('similarSelectedOverview');
    if (selOverview) selOverview.textContent = sel.overview || 'No overview available.';

    const selGenres = document.getElementById('similarSelectedGenres');
    if (selGenres) selGenres.textContent = sel.genres || sel.genres_str || 'General Cinema';

    const selDirector = document.getElementById('similarSelectedDirector');
    if (selDirector) selDirector.textContent = sel.director || 'Unknown';

    // Recommendations Grid
    const countBadge = document.getElementById('similarCountBadge');
    if (countBadge) countBadge.textContent = `${data.recommendations.length} Movies`;

    const gridContainer = document.getElementById('similarGridContainer');
    if (gridContainer) {
        gridContainer.innerHTML = '';
        data.recommendations.forEach(rec => {
            const cardCol = document.createElement('div');
            cardCol.className = 'col';

            const recPosterSrc = rec.poster_url || (rec.poster_path ? (rec.poster_path.startsWith('http') ? rec.poster_path : 'https://image.tmdb.org/t/p/w500' + rec.poster_path) : '');
            const hasPoster = Boolean(recPosterSrc);

            const simBadgeHtml = rec.similarity_label 
                ? (rec.similarity_percent 
                    ? `<div class="similarity-badge"><i class="fa-solid fa-chart-line me-1"></i> ${rec.similarity_percent}%</div>`
                    : `<div class="similarity-badge" style="border-color: #ffc107; color: #ffc107;"><i class="fa-solid fa-globe me-1"></i> TMDB</div>`)
                : '';

            const isSaved = Boolean(rec.is_in_watchlist);

            cardCol.innerHTML = `
                <div class="movie-poster-card rounded-3 overflow-hidden position-relative h-100">
                    <div class="poster-frame position-relative">
                        <div class="poster-badge-rating">
                            <i class="fa-solid fa-star text-warning me-1"></i>
                            ${rec.vote_average ? Number(rec.vote_average).toFixed(1) : '0.0'}
                        </div>
                        ${simBadgeHtml}
                        ${hasPoster 
                            ? `<img src="${recPosterSrc}" alt="${escapeHtml(rec.title)}" class="poster-img" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.classList.remove('d-none');">` 
                            : ''}
                        <div class="poster-svg-fallback ${hasPoster ? 'd-none' : ''}">
                            <i class="fa-solid fa-film text-cyan fs-2 mb-2 opacity-50"></i>
                            <span class="fs-2xs fw-bold text-white text-center px-1">${escapeHtml(rec.title)}</span>
                        </div>
                        <div class="poster-hover-overlay">
                            <div class="overlay-actions d-flex flex-column gap-2 p-2 w-100">
                                <button type="button" class="btn btn-cyan btn-sm rounded-pill w-100 btn-movie-details py-1 fs-2xs" data-movie-id="${rec.id}">
                                    <i class="fa-solid fa-circle-info me-1"></i> Details
                                </button>
                                <button type="button" class="btn ${isSaved ? 'btn-success' : 'btn-outline-light'} btn-sm rounded-pill w-100 btn-watchlist-toggle py-1 fs-2xs" 
                                        data-movie-id="${rec.id}" 
                                        data-poster-path="${rec.poster_path || ''}"
                                        data-is-added="${isSaved ? 'true' : 'false'}">
                                    <i class="${isSaved ? 'fa-solid' : 'fa-regular'} fa-bookmark me-1"></i> 
                                    ${isSaved ? 'Saved' : 'Watchlist'}
                                </button>
                                <button type="button" class="btn btn-outline-cyan btn-sm rounded-pill w-100 btn-movie-similar py-1 fs-2xs" 
                                        data-movie-id="${rec.id}" 
                                        data-movie-title="${escapeHtml(rec.title)}">
                                    <i class="fa-solid fa-wand-magic-sparkles me-1"></i> Similar
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="poster-info pt-2 px-1">
                        <h6 class="poster-title font-outfit text-white text-truncate mb-1 fs-xs" title="${escapeHtml(rec.title)}">${escapeHtml(rec.title)}</h6>
                        <div class="d-flex align-items-center justify-content-between text-secondary fs-2xs mb-1">
                            <span>${rec.release_year || 'N/A'}</span>
                            <span class="badge bg-dark-subtle text-cyan fs-3xs">${escapeHtml(rec.director || 'Film')}</span>
                        </div>
                        <div class="text-secondary fs-3xs text-truncate">${escapeHtml(rec.genres_str || rec.genres || '')}</div>
                    </div>
                </div>
            `;
            gridContainer.appendChild(cardCol);
        });
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
