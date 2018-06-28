var jQuery = require( 'jquery' ),
    $ = jQuery,
    QUERY_STRING = require( 'utils/query-string-parsing' ),
    Ui = require( 'mvc/ui/ui-misc' );

var Router = Backbone.Router.extend({
    // TODO: not many client routes at this point - fill and remove from server.
    // since we're at root here, this may be the last to be routed entirely on the client.
    initialize : function( page, options ){
        this.page = page;
        this.options = options;
    },

    /** helper to push a new navigation state */
    push: function( url, data ) {
        data = data || {};
        data.__identifer = Math.random().toString( 36 ).substr( 2 );
        if ( !$.isEmptyObject( data ) ) {
            url += url.indexOf( '?' ) == -1 ? '?' : '&';
            url += $.param( data , true );
        }
        Galaxy.params = data;
        this.navigate( url, { 'trigger': true } );
    },

    /** override to parse query string into obj and send to each route */
    execute: function( callback, args, name ){
        Galaxy.debug( 'router execute:', callback, args, name );
        var queryObj = QUERY_STRING.parse( args.pop() );
        args.push( queryObj );
        if( callback ){
            if ( this.authenticate( args, name ) ) {
                callback.apply( this, args );
            } else {
                this.access_denied();
            }
        }
    },

    authenticate: function( args, name ) {
        return true;
    },

    access_denied: function() {
        this.page.display( new Ui.Message( { status: 'danger', message: 'You must be logged in with proper credentials to make this request.', persistent: true } ) );
    }
});

module.exports = Router