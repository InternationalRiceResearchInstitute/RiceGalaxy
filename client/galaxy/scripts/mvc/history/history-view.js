define([
    "mvc/list/list-view",
    "mvc/history/history-model",
    "mvc/history/history-contents",
    "mvc/history/history-preferences",
    "mvc/history/hda-li",
    "mvc/history/hdca-li",
    "mvc/user/user-model",
    "mvc/ui/error-modal",
    "ui/fa-icon-button",
    "mvc/base-mvc",
    "utils/localization",
    "ui/search-input"
], function(
    LIST_VIEW,
    HISTORY_MODEL,
    HISTORY_CONTENTS,
    HISTORY_PREFS,
    HDA_LI,
    HDCA_LI,
    USER,
    ERROR_MODAL,
    faIconButton,
    BASE_MVC,
    _l
){
'use strict';

/* =============================================================================
TODO:

============================================================================= */
/** @class  non-editable, read-only View/Controller for a history model.
 *  Allows:
 *      changing the loaded history
 *      displaying data, info, and download
 *      tracking history attrs: size, tags, annotations, name, etc.
 *  Does not allow:
 *      changing the name
 */
var _super = LIST_VIEW.ModelListPanel;
var HistoryView = _super.extend(
/** @lends HistoryView.prototype */{
    _logNamespace : 'history',

    /** class to use for constructing the HDA views */
    HDAViewClass        : HDA_LI.HDAListItemView,
    /** class to use for constructing the HDCA views */
    HDCAViewClass       : HDCA_LI.HDCAListItemView,
    /** class to used for constructing collection of sub-view models */
    collectionClass     : HISTORY_CONTENTS.HistoryContents,
    /** key of attribute in model to assign to this.collection */
    modelCollectionKey  : 'contents',

    tagName             : 'div',
    className           : _super.prototype.className + ' history-panel',

    /** string to display when the collection is empty */
    emptyMsg            : _l( 'This history is empty' ),
    /** displayed when no items match the search terms */
    noneFoundMsg        : _l( 'No matching datasets found' ),
    /** string used for search placeholder */
    searchPlaceholder   : _l( 'search datasets' ),

    /** @type {Number} ms to wait after history load to fetch/decorate hdcas with element_count */
    FETCH_COLLECTION_COUNTS_DELAY : 2000,

    // ......................................................................... SET UP
    /** Set up the view, bind listeners.
     *  @param {Object} attributes optional settings for the panel
     */
    initialize : function( attributes ){
        _super.prototype.initialize.call( this, attributes );
        // ---- instance vars
        // control contents/behavior based on where (and in what context) the panel is being used
        /** where should pages from links be displayed? (default to new tab/window) */
        this.linkTarget = attributes.linkTarget || '_blank';
    },

    /** create and return a collection for when none is initially passed */
    _createDefaultCollection : function(){
        // override
        return new this.collectionClass([], { history: this.model });
    },

    /** In this override, clear the update timer on the model */
    freeModel : function(){
        _super.prototype.freeModel.call( this );
        if( this.model ){
            this.model.clearUpdateTimeout();
        }
        return this;
    },

    /** create any event listeners for the panel
     *  @fires: rendered:initial    on the first render
     *  @fires: empty-history       when switching to a history with no contents or creating a new history
     */
    _setUpListeners : function(){
        _super.prototype._setUpListeners.call( this );
        this.on({
            error : function( model, xhr, options, msg, details ){
                this.errorHandler( model, xhr, options, msg, details );
            },
            'loading-done' : function(){
                var self = this;
                // after the initial load, decorate with more time consuming fields (like HDCA element_counts)
                _.delay( function(){
                    self.model.contents.fetchCollectionCounts();
                }, self.FETCH_COLLECTION_COUNTS_DELAY );
            },
            'views:ready view:attached view:removed' : function( view ){
                this._renderSelectButton();
            },
            'view:attached' : function( view ){
                this.scrollTo(0);
            },
        });
        // this.on( 'all', function(){ console.debug( arguments ); });
    },

    // ------------------------------------------------------------------------ loading history/hda models
    /** load the history with the given id then it's contents, sending ajax options to both */
    loadHistory : function( historyId, options, contentsOptions ){
        contentsOptions = _.extend( contentsOptions || { silent: true });
        this.info( 'loadHistory:', historyId, options, contentsOptions );
        var self = this;
        self.setModel( new HISTORY_MODEL.History({ id : historyId }) );

        contentsOptions.silent = true;
        self.trigger( 'loading' );
        return self.model
            .fetchWithContents( options, contentsOptions )
            .always( function(){
                self.render();
                self.trigger( 'loading-done' );
            });
    },

    /** convenience alias to the model. Updates the item list only (not the history) */
    refreshContents : function( options ){
        if( this.model ){
            return this.model.refresh( options );
        }
        // may have callbacks - so return an empty promise
        return $.when();
    },

    /** Override to reset web storage when the id changes (since it needs the id) */
    _setUpCollectionListeners : function(){
        _super.prototype._setUpCollectionListeners.call( this );
        return this.listenTo( this.collection, {
            // 'all' : function(){ console.log( this.collection + ':', arguments ); },
            'fetching-more'     : function(){
                this._toggleContentsLoadingIndicator( true );
                this.$emptyMessage().hide();
            },
            'fetching-more-done': function(){ this._toggleContentsLoadingIndicator( false ); },
        });
    },

    // ------------------------------------------------------------------------ panel rendering
    /** hide the $el and display a loading indicator (in the $el's parent) when loading new data */
    _showLoadingIndicator : function( msg, speed, callback ){
        var $indicator = $( '<div class="loading-indicator"/>' );
        this.$el.html( $indicator.text( msg ).slideDown( !_.isUndefined( speed )? speed : this.fxSpeed ) );
    },

    /** hide the loading indicator */
    _hideLoadingIndicator : function( speed ){
        // make speed a bit slower to compensate for slow rendering of up to 500 contents
        this.$( '.loading-indicator' ).slideUp( !_.isUndefined( speed )? speed : ( this.fxSpeed + 200 ), function(){
            $( this ).remove();
        });
    },

    /** In this override, add a btn to toggle the selectors */
    _buildNewRender : function(){
        var $newRender = _super.prototype._buildNewRender.call( this );
        this._renderSelectButton( $newRender );
        return $newRender;
    },

    /** button for starting select mode */
    _renderSelectButton : function( $where ){
        $where = $where || this.$el;
        // do not render selector option if no actions
        if( !this.multiselectActions().length ){
            return null;
        }
        // do not render (and remove even) if nothing to select
        if( !this.views.length ){
            this.hideSelectors();
            $where.find( '.controls .actions .show-selectors-btn' ).remove();
            return null;
        }
        // don't bother rendering if there's one already
        var $existing = $where.find( '.controls .actions .show-selectors-btn' );
        if( $existing.length ){
            return $existing;
        }

        return faIconButton({
            title   : _l( 'Operations on multiple datasets' ),
            classes : 'show-selectors-btn',
            faIcon  : 'fa-check-square-o'
        }).prependTo( $where.find( '.controls .actions' ) );
    },

    /** override to avoid showing intial empty message using contents_active */
    _renderEmptyMessage : function( $whereTo ){
        var self = this;
        var $emptyMsg = self.$emptyMessage( $whereTo );

        var empty = self.model.get( 'contents_active' ).active <= 0;
        if( empty ){
            return $emptyMsg.empty().append( self.emptyMsg ).show();

        } else if( self.searchFor && self.model.contents.haveSearchDetails() && !self.views.length ){
            return $emptyMsg.empty().append( self.noneFoundMsg ).show();
        }
        $emptyMsg.hide();
        return $();
    },

    /** the scroll container for this panel - can be $el, $el.parent(), or grandparent depending on context */
    $scrollContainer : function( $where ){
        // override or set via attributes.$scrollContainer
        return this.$list( $where );
    },

    // ------------------------------------------------------------------------ subviews
    _toggleContentsLoadingIndicator : function( show ){
        if( !show ){
            this.$list().find( '.contents-loading-indicator' ).remove();
        } else {
            this.$list().html( '<div class="contents-loading-indicator">'
                + '<span class="fa fa-2x fa-spinner fa-spin"/></div>' );
        }
    },

    /** override to render pagination also */
    renderItems: function( $whereTo ){
        // console.log( this + '.renderItems-----------------', new Date() );
        $whereTo = $whereTo || this.$el;
        var self = this;
        var $list = self.$list( $whereTo );

        // TODO: bootstrap hack to remove orphaned tooltips
        $( '.tooltip' ).remove();

        $list.empty();
        self.views = [];

        var models = self._filterCollection();
        if( models.length ){
            self._renderPagination( $whereTo );
            self.views = self._renderSomeItems( models, $list );
        } else {
            // TODO: consolidate with _renderPagination above by (???) passing in models/length?
            $whereTo.find( '> .controls .list-pagination' ).empty();
        }
        self._renderEmptyMessage( $whereTo ).toggle( !models.length );

        self.trigger( 'views:ready', self.views );
        return self.views;
    },

    /** render pagination controls if not searching and contents says we're paginating */
    _renderPagination: function( $whereTo ){
        var $paginationControls = $whereTo.find( '> .controls .list-pagination' );
        if( this.searchFor || !this.model.contents.shouldPaginate() ) return $paginationControls.empty();

        $paginationControls.html( this.templates.pagination({
            // pagination is 1-based for the user
            current : this.model.contents.currentPage + 1,
            last    : this.model.contents.getLastPage() + 1,
        }, this ));
        $paginationControls.find( 'select.pages' ).tooltip();
        return $paginationControls;
    },

    /** render a subset of the entire collection (client-side pagination) */
    _renderSomeItems: function( models, $list ){
        var self = this;
        var views = [];
        $list.append( models.map( function( m ){
            var view = self._createItemView( m );
            views.push( view );
            return self._renderItemView$el( view );
        }));
        return views;
    },

    // ------------------------------------------------------------------------ sub-views
    /** in this override, check if the contents would also display based on includeDeleted/hidden */
    _filterItem : function( model ){
        var self = this;
        var contents = self.model.contents;
        return ( contents.includeHidden  || !model.hidden() )
            && ( contents.includeDeleted || !model.isDeletedOrPurged() )
            && ( _super.prototype._filterItem.call( self, model ) );
    },

    /** In this override, since history contents are mixed,
     *      get the appropo view class based on history_content_type
     */
    _getItemViewClass : function( model ){
        var contentType = model.get( "history_content_type" );
        switch( contentType ){
            case 'dataset':
                return this.HDAViewClass;
            case 'dataset_collection':
                return this.HDCAViewClass;
        }
        throw new TypeError( 'Unknown history_content_type: ' + contentType );
    },

    /** in this override, add a linktarget, and expand if id is in web storage */
    _getItemViewOptions : function( model ){
        var options = _super.prototype._getItemViewOptions.call( this, model );
        return _.extend( options, {
            linkTarget      : this.linkTarget,
            expanded        : this.model.contents.storage.isExpanded( model.id ),
            hasUser         : this.model.ownedByCurrUser()
        });
    },

    /** In this override, add/remove expanded/collapsed model ids to/from web storage */
    _setUpItemViewListeners : function( view ){
        var panel = this;
        _super.prototype._setUpItemViewListeners.call( panel, view );
        //TODO: send from content view: this.model.collection.storage.addExpanded
        // maintain a list of items whose bodies are expanded
        return panel.listenTo( view, {
            'expanded': function( v ){
                panel.model.contents.storage.addExpanded( v.model );
            },
            'collapsed': function( v ){
                panel.model.contents.storage.removeExpanded( v.model );
            }
        });
    },

    /** override to remove expandedIds from webstorage */
    collapseAll : function(){
        this.model.contents.storage.clearExpanded();
        _super.prototype.collapseAll.call( this );
    },

    // ------------------------------------------------------------------------ selection
    /** Override to correctly set the historyId of the new collection */
    getSelectedModels : function(){
        var collection = _super.prototype.getSelectedModels.call( this );
        collection.historyId = this.collection.historyId;
        return collection;
    },


    // ------------------------------------------------------------------------ panel events
    /** event map */
    events : _.extend( _.clone( _super.prototype.events ), {
        'click .show-selectors-btn'         : 'toggleSelectors',
        'click > .controls .prev'           : '_clickPrevPage',
        'click > .controls .next'           : '_clickNextPage',
        'change > .controls .pages'         : '_changePageSelect',
        // allow (error) messages to be clicked away
        'click .messages [class$=message]'  : 'clearMessages',
    }),

    _clickPrevPage : function( ev ){
        this.model.clearUpdateTimeout();
        this.model.contents.fetchPrevPage();
    },

    _clickNextPage : function( ev ){
        this.model.clearUpdateTimeout();
        this.model.contents.fetchNextPage();
    },

    _changePageSelect : function( ev ){
        this.model.clearUpdateTimeout();
        var page = $( ev.currentTarget ).val();
        this.model.contents.fetchPage( page );
    },

    /** Toggle and store the deleted visibility and re-render items
     * @returns {Boolean} new setting
     */
    toggleShowDeleted : function( show, options ){
        show = ( show !== undefined )?( show ):( !this.model.contents.includeDeleted );
        var self = this;
        var contents = self.model.contents;
        contents.setIncludeDeleted( show, options );
        self.trigger( 'show-deleted', show );

        contents.fetchCurrentPage({ renderAll: true });
        return show;
    },

    /** Toggle and store whether to render explicity hidden contents
     * @returns {Boolean} new setting
     */
    toggleShowHidden : function( show, store, options ){
        // console.log( 'toggleShowHidden', show, store );
        show = ( show !== undefined )?( show ):( !this.model.contents.includeHidden );
        var self = this;
        var contents = self.model.contents;
        contents.setIncludeHidden( show, options );
        self.trigger( 'show-hidden', show );

        contents.fetchCurrentPage({ renderAll: true });
        return show;
    },

    /** On the first search, if there are no details - load them, then search */
    _firstSearch : function( searchFor ){
        var self = this;
        var inputSelector = '> .controls .search-input';
        this.log( 'onFirstSearch', searchFor );

        // if the contents already have enough details to search, search and return now
        if( self.model.contents.haveSearchDetails() ){
            self.searchItems( searchFor );
            return;
        }

        // otherwise, load the details progressively here
        self.$( inputSelector ).searchInput( 'toggle-loading' );
        // set this now so that only results will show during progress
        self.searchFor = searchFor;
        var xhr = self.model.contents.progressivelyFetchDetails({ silent: true })
            .progress( function( response, limit, offset ){
                self.renderItems();
                self.trigger( 'search:loading-progress', limit, offset );
            })
            .always( function(){
                self.$el.find( inputSelector ).searchInput( 'toggle-loading' );
            })
            .done( function(){
                self.searchItems( searchFor, 'force' );
           });
    },

    /** clear the search filters and show all views that are normally shown */
    clearSearch : function( searchFor ){
        var self = this;
        if( !self.searchFor ) return self;
        //self.log( 'onSearchClear', self );
        self.searchFor = '';
        self.trigger( 'search:clear', self );
        self.$( '> .controls .search-query' ).val( '' );
        // NOTE: silent + render prevents collection update event with merge only
        // - which causes an empty page due to event handler above
        self.model.contents.fetchCurrentPage({ silent: true })
            .done( function(){
                self.renderItems();
            });
        return self;
    },

    // ........................................................................ error handling
    /** Event handler for errors (from the panel, the history, or the history's contents)
     *  Alternately use two strings for model and xhr to use custom message and title (respectively)
     *  @param {Model or View} model    the (Backbone) source of the error
     *  @param {XMLHTTPRequest} xhr     any ajax obj. assoc. with the error
     *  @param {Object} options         the options map commonly used with bbone ajax
     */
    errorHandler : function( model, xhr, options ){
        //TODO: to mixin or base model
        // interrupted ajax or no connection
        if( xhr && xhr.status === 0 && xhr.readyState === 0 ){
            // return ERROR_MODAL.offlineErrorModal();
            // fail silently
            return;
        }
        // otherwise, leave something to report in the console
        this.error( model, xhr, options );
        // and feedback to a modal
        // if sent two strings (and possibly details as 'options'), use those as message and title
        if( _.isString( model ) && _.isString( xhr ) ){
            var message = model;
            var title = xhr;
            return ERROR_MODAL.errorModal( message, title, options );
        }
        // bad gateway
        // TODO: possibly to global handler
        if( xhr && xhr.status === 502 ){
            return ERROR_MODAL.badGatewayErrorModal();
        }
        return ERROR_MODAL.ajaxErrorModal( model, xhr, options );
    },

    /** Remove all messages from the panel. */
    clearMessages : function( ev ){
        var $target = !_.isUndefined( ev )?
            $( ev.currentTarget )
            :this.$messages().children( '[class$="message"]' );
        $target.fadeOut( this.fxSpeed, function(){
            $( this ).remove();
        });
        return this;
    },

    // ........................................................................ scrolling
    /** Scrolls the panel to show the content sub-view with the given hid.
     *  @param {Integer} hid    the hid of item to scroll into view
     *  @returns {HistoryView} the panel
     */
    scrollToHid : function( hid ){
        return this.scrollToItem( _.first( this.viewsWhereModel({ hid: hid }) ) );
    },

    // ........................................................................ misc
    /** utility for adding -st, -nd, -rd, -th to numbers */
    ordinalIndicator : function( number ){
        var numStr = number + '';
        switch( numStr.charAt( numStr.length - 1 )){
            case '1': return numStr + 'st';
            case '2': return numStr + 'nd';
            case '3': return numStr + 'rd';
            default : return numStr + 'th';
        }
    },

    /** Return a string rep of the history */
    toString : function(){
        return 'HistoryView(' + (( this.model )?( this.model.get( 'name' )):( '' )) + ')';
    }
});


//------------------------------------------------------------------------------ TEMPLATES
HistoryView.prototype.templates = (function(){

    var mainTemplate = BASE_MVC.wrapTemplate([
        // temp container
        '<div>',
            '<div class="controls"></div>',
            '<ul class="list-items"></ul>',
            '<div class="empty-message infomessagesmall"></div>',
        '</div>'
    ]);

    var controlsTemplate = BASE_MVC.wrapTemplate([
        '<div class="controls">',
            '<div class="title">',
                '<div class="name"><%- history.name %></div>',
            '</div>',
            '<div class="subtitle"></div>',
            '<div class="history-size"><%- history.nice_size %></div>',

            '<div class="actions"></div>',

            '<div class="messages">',
                '<% if( history.deleted && history.purged ){ %>',
                    '<div class="deleted-msg warningmessagesmall">',
                        _l( 'This history has been purged and deleted' ),
                    '</div>',
                '<% } else if( history.deleted ){ %>',
                    '<div class="deleted-msg warningmessagesmall">',
                        _l( 'This history has been deleted' ),
                    '</div>',
                '<% } else if( history.purged ){ %>',
                    '<div class="deleted-msg warningmessagesmall">',
                        _l( 'This history has been purged' ),
                    '</div>',
                '<% } %>',

                '<% if( history.message ){ %>',
                    // should already be localized
                    '<div class="<%= history.message.level || "info" %>messagesmall">',
                        '<%= history.message.text %>',
                    '</div>',
                '<% } %>',
            '</div>',

            // add tags and annotations
            '<div class="tags-display"></div>',
            '<div class="annotation-display"></div>',

            '<div class="search">',
                '<div class="search-input"></div>',
            '</div>',

            '<div class="list-actions">',
                '<div class="btn-group">',
                    '<button class="select-all btn btn-default"',
                            'data-mode="select">', _l( 'All' ), '</button>',
                    '<button class="deselect-all btn btn-default"',
                            'data-mode="select">', _l( 'None' ), '</button>',
                '</div>',
                '<div class="list-action-menu btn-group">',
                '</div>',
            '</div>',
            '<div class="list-pagination form-inline"></div>',
        '</div>'
    ], 'history' );

    var paginationTemplate = BASE_MVC.wrapTemplate([
        '<button class="prev" <%- pages.current === 1 ? "disabled" : "" %>>previous</button>',
        '<select class="pages form-control" ',
                'title="', _l( 'Click to open and select a page. Begin typing a page number to select it' ), '">',
            '<% _.range( 1, pages.last + 1 ).forEach( function( i ){ %>',
                '<option value="<%- i - 1 %>" <%- i === pages.current ? "selected" : "" %>>',
                    '<%- view.ordinalIndicator( i ) %> of <%- pages.last %> pages',
                '</option>',
            '<% }); %>',
        '</select>',
        '<button class="next" <%- pages.current === pages.last ? "disabled" : "" %>>next</button>',
    ], 'pages' );

    return _.extend( _.clone( _super.prototype.templates ), {
        el                      : mainTemplate,
        controls                : controlsTemplate,
        pagination              : paginationTemplate,
    });
}());


//==============================================================================
    return {
        HistoryView: HistoryView
    };
});
