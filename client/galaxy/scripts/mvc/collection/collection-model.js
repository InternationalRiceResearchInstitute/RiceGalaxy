define([
    "mvc/dataset/dataset-model",
    "mvc/base-mvc",
    "utils/localization"
], function( DATASET_MODEL, BASE_MVC, _l ){
'use strict';

//==============================================================================
/*
Notes:

Terminology:
    DatasetCollection/DC : a container of datasets or nested DatasetCollections
    Element/DatasetCollectionElement/DCE : an item contained in a DatasetCollection
    HistoryDatasetCollectionAssociation/HDCA: a DatasetCollection contained in a history


This all seems too complex unfortunately:

- Terminology collision between DatasetCollections (DCs) and Backbone Collections.
- In the DatasetCollections API JSON, DC Elements use a 'Has A' stucture to *contain*
    either a dataset or a nested DC. This would make the hierarchy much taller. I've
    decided to merge the contained JSON with the DC element json - making the 'has a'
    relation into an 'is a' relation. This seems simpler to me and allowed a lot of
    DRY in both models and views, but may make tracking or tracing within these models
    more difficult (since DatasetCollectionElements are now *also* DatasetAssociations
    or DatasetCollections (nested)). This also violates the rule of thumb about
    favoring aggregation over inheritance.
- Currently, there are three DatasetCollection subclasses: List, Pair, and ListPaired.
    These each should a) be usable on their own, b) be usable in the context of
    nesting within a collection model (at least in the case of ListPaired), and
    c) be usable within the context of other container models (like History or
    LibraryFolder, etc.). I've tried to separate/extract classes in order to
    handle those three situations, but it's proven difficult to do in a simple,
    readable manner.
- Ideally, histories and libraries would inherit from the same server models as
    dataset collections do since they are (in essence) dataset collections themselves -
    making the whole nested structure simpler. This would be a large, error-prone
    refactoring and migration.

Many of the classes and heirarchy are meant as extension points so, while the
relations and flow may be difficult to understand initially, they'll allow us to
handle the growth or flux dataset collection in the future (w/o actually implementing
any YAGNI).

*/
//_________________________________________________________________________________________________ ELEMENTS
/** @class mixin for Dataset collection elements.
 *      When collection elements are passed from the API, the underlying element is
 *          in a sub-object 'object' (IOW, a DCE representing an HDA will have HDA json in element.object).
 *      This mixin uses the constructor and parse methods to merge that JSON with the DCE attribtues
 *          effectively changing a DCE from a container to a subclass (has a --> is a).
 */
var DatasetCollectionElementMixin = {

    /** default attributes used by elements in a dataset collection */
    defaults : {
        model_class         : 'DatasetCollectionElement',
        element_identifier  : null,
        element_index       : null,
        element_type        : null
    },

    /** merge the attributes of the sub-object 'object' into this model */
    _mergeObject : function( attributes ){
        // if we don't preserve and correct ids here, the element id becomes the object id
        // and collision in backbone's _byId will occur and only
        _.extend( attributes, attributes.object, { element_id: attributes.id });
        delete attributes.object;
        return attributes;
    },

    /** override to merge this.object into this */
    constructor : function( attributes, options ){
        // console.debug( '\t DatasetCollectionElement.constructor:', attributes, options );
        attributes = this._mergeObject( attributes );
        this.idAttribute = 'element_id';
        Backbone.Model.apply( this, arguments );
    },

    /** when the model is fetched, merge this.object into this */
    parse : function( response, options ){
        var attributes = response;
        attributes = this._mergeObject( attributes );
        return attributes;
    }
};

/** @class Concrete class of Generic DatasetCollectionElement */
var DatasetCollectionElement = Backbone.Model
    .extend( BASE_MVC.LoggableMixin )
    .extend( DatasetCollectionElementMixin )
    .extend({ _logNamespace : 'collections' });


//==============================================================================
/** @class Base/Abstract Backbone collection for Generic DCEs. */
var DCECollection = Backbone.Collection.extend( BASE_MVC.LoggableMixin ).extend(
/** @lends DCECollection.prototype */{
    _logNamespace : 'collections',

    model: DatasetCollectionElement,

    /** String representation. */
    toString : function(){
         return ([ 'DatasetCollectionElementCollection(', this.length, ')' ].join( '' ));
    }
});


//==============================================================================
/** @class Backbone model for a dataset collection element that is a dataset (HDA).
 */
var DatasetDCE = DATASET_MODEL.DatasetAssociation.extend( BASE_MVC.mixin( DatasetCollectionElementMixin,
/** @lends DatasetDCE.prototype */{

    /** url fn */
    url : function(){
        // won't always be an hda
        if( !this.has( 'history_id' ) ){
            console.warn( 'no endpoint for non-hdas within a collection yet' );
            // (a little silly since this api endpoint *also* points at hdas)
            return Galaxy.root + 'api/datasets';
        }
        return Galaxy.root + 'api/histories/' + this.get( 'history_id' ) + '/contents/' + this.get( 'id' );
    },

    defaults : _.extend( {},
        DATASET_MODEL.DatasetAssociation.prototype.defaults,
        DatasetCollectionElementMixin.defaults
    ),

    _downloadQueryParameters : function() {
        return '?to_ext=' + this.get( 'file_ext' ) + '&hdca_id=' + this.get( 'parent_hdca_id' ) + '&element_identifier=' + this.get( 'element_identifier' );
    },

    // because all objects have constructors (as this hashmap would even if this next line wasn't present)
    //  the constructor in hcontentMixin won't be attached by BASE_MVC.mixin to this model
    //  - re-apply manually for now
    /** call the mixin constructor */
    constructor : function( attributes, options ){
        this.debug( '\t DatasetDCE.constructor:', attributes, options );
        //DATASET_MODEL.DatasetAssociation.prototype.constructor.call( this, attributes, options );
        DatasetCollectionElementMixin.constructor.call( this, attributes, options );
    },

    /** Does this model already contain detailed data (as opposed to just summary level data)? */
    hasDetails : function(){
        return this.elements && this.elements.length;
    },

    /** String representation. */
    toString : function(){
        var objStr = this.get( 'element_identifier' );
        return ([ 'DatasetDCE(', objStr, ')' ].join( '' ));
    }
}));


//==============================================================================
/** @class DCECollection of DatasetDCE's (a list of datasets, a pair of datasets).
 */
var DatasetDCECollection = DCECollection.extend(
/** @lends DatasetDCECollection.prototype */{
    model: DatasetDCE,

    /** String representation. */
    toString : function(){
         return ([ 'DatasetDCECollection(', this.length, ')' ].join( '' ));
    }
});


//_________________________________________________________________________________________________ COLLECTIONS
/** @class Backbone model for Dataset Collections.
 *      The DC API returns an array of JSON objects under the attribute elements.
 *      This model:
 *          - removes that array/attribute ('elements') from the model,
 *          - creates a bbone collection (of the class defined in the 'collectionClass' attribute),
 *          - passes that json onto the bbone collection
 *          - caches the bbone collection in this.elements
 */
var DatasetCollection = Backbone.Model
        .extend( BASE_MVC.LoggableMixin )
        .extend( BASE_MVC.SearchableModelMixin )
        .extend(/** @lends DatasetCollection.prototype */{
    _logNamespace : 'collections',

    /** default attributes for a model */
    defaults : {
        /* 'list', 'paired', or 'list:paired' */
        collection_type     : null,
        //??
        deleted             : false
    },

    /** Which class to use for elements */
    collectionClass : DCECollection,

    /** set up: create elements instance var and (on changes to elements) update them  */
    initialize : function( model, options ){
        this.debug( this + '(DatasetCollection).initialize:', model, options, this );
        this.elements = this._createElementsModel();
        this.on( 'change:elements', function(){
            this.log( 'change:elements' );
            //TODO: prob. better to update the collection instead of re-creating it
            this.elements = this._createElementsModel();
        });
    },

    /** move elements model attribute to full collection */
    _createElementsModel : function(){
        this.debug( this + '._createElementsModel', this.collectionClass, this.get( 'elements' ), this.elements );
        //TODO: same patterns as DatasetCollectionElement _createObjectModel - refactor to BASE_MVC.hasSubModel?
        var elements = this.get( 'elements' ) || [];
        this.unset( 'elements', { silent: true });
        var self = this;
        _.each(elements, function(element, index) {
            _.extend(element, {"parent_hdca_id": self.get("id")});
        });
        this.elements = new this.collectionClass( elements );
        //this.debug( 'collectionClass:', this.collectionClass + '', this.elements );
        return this.elements;
    },

    // ........................................................................ common queries
    /** pass the elements back within the model json when this is serialized */
    toJSON : function(){
        var json = Backbone.Model.prototype.toJSON.call( this );
        if( this.elements ){
            json.elements = this.elements.toJSON();
        }
        return json;
    },

    /** Is this collection in a 'ready' state no processing (for the collection) is left
     *  to do on the server.
     */
    inReadyState : function(){
        var populated = this.get( 'populated' );
        return ( this.isDeletedOrPurged() || populated );
    },

    //TODO:?? the following are the same interface as DatasetAssociation - can we combine?
    /** Does the DC contain any elements yet? Is a fetch() required? */
    hasDetails : function(){
        return this.elements.length !== 0;
    },

    /** Given the filters, what models in this.elements would be returned? */
    getVisibleContents : function( filters ){
        // filters unused for now
        return this.elements;
    },

    // ........................................................................ ajax
    /** override to use actual Dates objects for create/update times */
    parse : function( response, options ){
        var parsed = Backbone.Model.prototype.parse.call( this, response, options );
        if( parsed.create_time ){
            parsed.create_time = new Date( parsed.create_time );
        }
        if( parsed.update_time ){
            parsed.update_time = new Date( parsed.update_time );
        }
        return parsed;
    },

    /** save this dataset, _Mark_ing it as deleted (just a flag) */
    'delete' : function( options ){
        if( this.get( 'deleted' ) ){ return jQuery.when(); }
        return this.save( { deleted: true }, options );
    },
    /** save this dataset, _Mark_ing it as undeleted */
    undelete : function( options ){
        if( !this.get( 'deleted' ) || this.get( 'purged' ) ){ return jQuery.when(); }
        return this.save( { deleted: false }, options );
    },

    /** Is this collection deleted or purged? */
    isDeletedOrPurged : function(){
        return ( this.get( 'deleted' ) || this.get( 'purged' ) );
    },

    // ........................................................................ searchable
    /** searchable attributes for collections */
    searchAttributes : [
        'name', 'tags'
    ],

    // ........................................................................ misc
    /** String representation */
    toString : function(){
        var idAndName = [ this.get( 'id' ), this.get( 'name' ) || this.get( 'element_identifier' ) ];
        return 'DatasetCollection(' + ( idAndName.join(',') ) + ')';
    }
});


//==============================================================================
/** Model for a DatasetCollection containing datasets (non-nested).
 */
var ListDatasetCollection = DatasetCollection.extend(
/** @lends ListDatasetCollection.prototype */{

    /** override since we know the collection will only contain datasets */
    collectionClass : DatasetDCECollection,

    /** String representation. */
    toString : function(){ return 'List' + DatasetCollection.prototype.toString.call( this ); }
});


//==============================================================================
/** Model for a DatasetCollection containing fwd/rev datasets (a list of 2).
 */
var PairDatasetCollection = ListDatasetCollection.extend(
/** @lends PairDatasetCollection.prototype */{

    /** String representation. */
    toString : function(){ return 'Pair' + DatasetCollection.prototype.toString.call( this ); }
});


//_________________________________________________________________________________________________ NESTED COLLECTIONS
// this is where things get weird, man. Weird.
//TODO: it might be possible to compact all the following...I think.
//==============================================================================
/** @class Backbone model for a Generic DatasetCollectionElement that is also a DatasetCollection
 *      (a nested collection). Currently only list:paired.
 */
var NestedDCDCE = DatasetCollection.extend( BASE_MVC.mixin( DatasetCollectionElementMixin,
/** @lends NestedDCDCE.prototype */{

    // because all objects have constructors (as this hashmap would even if this next line wasn't present)
    //  the constructor in hcontentMixin won't be attached by BASE_MVC.mixin to this model
    //  - re-apply manually it now
    /** call the mixin constructor */
    constructor : function( attributes, options ){
        this.debug( '\t NestedDCDCE.constructor:', attributes, options );
        DatasetCollectionElementMixin.constructor.call( this, attributes, options );
    },

    /** String representation. */
    toString : function(){
        var objStr = ( this.object )?( '' + this.object ):( this.get( 'element_identifier' ) );
        return ([ 'NestedDCDCE(', objStr, ')' ].join( '' ));
    }
}));


//==============================================================================
/** @class Backbone collection containing Generic NestedDCDCE's (nested dataset collections).
 */
var NestedDCDCECollection = DCECollection.extend(
/** @lends NestedDCDCECollection.prototype */{

    /** This is a collection of nested collections */
    model: NestedDCDCE,

    /** String representation. */
    toString : function(){
         return ([ 'NestedDCDCECollection(', this.length, ')' ].join( '' ));
    }
});


//==============================================================================
/** @class Backbone model for a paired dataset collection within a list:paired dataset collection.
 */
var NestedPairDCDCE = PairDatasetCollection.extend( BASE_MVC.mixin( DatasetCollectionElementMixin,
/** @lends NestedPairDCDCE.prototype */{
//TODO:?? possibly rename to NestedDatasetCollection?

    // because all objects have constructors (as this hashmap would even if this next line wasn't present)
    //  the constructor in hcontentMixin won't be attached by BASE_MVC.mixin to this model
    //  - re-apply manually it now
    /** This is both a collection and a collection element - call the constructor */
    constructor : function( attributes, options ){
        this.debug( '\t NestedPairDCDCE.constructor:', attributes, options );
        //DatasetCollection.constructor.call( this, attributes, options );
        DatasetCollectionElementMixin.constructor.call( this, attributes, options );
    },

    /** String representation. */
    toString : function(){
        var objStr = ( this.object )?( '' + this.object ):( this.get( 'element_identifier' ) );
        return ([ 'NestedPairDCDCE(', objStr, ')' ].join( '' ));
    }
}));


//==============================================================================
/** @class Backbone collection for a backbone collection containing paired dataset collections.
 */
var NestedPairDCDCECollection = NestedDCDCECollection.extend(
/** @lends PairDCDCECollection.prototype */{

    /** We know this collection is composed of only nested pair collections */
    model: NestedPairDCDCE,

    /** String representation. */
    toString : function(){
         return ([ 'NestedPairDCDCECollection(', this.length, ')' ].join( '' ));
    }
});


//==============================================================================
/** @class Backbone Model for a DatasetCollection (list) that contains DatasetCollections (pairs).
 */
var ListPairedDatasetCollection = DatasetCollection.extend(
/** @lends ListPairedDatasetCollection.prototype */{

    /** list:paired is the only collection that itself contains collections */
    collectionClass : NestedPairDCDCECollection,

    /** String representation. */
    toString : function(){
         return ([ 'ListPairedDatasetCollection(', this.get( 'name' ), ')' ].join( '' ));
    }
});


//==============================================================================
/** @class Backbone model for a list dataset collection within a list:list dataset collection. */
var NestedListDCDCE = ListDatasetCollection.extend( BASE_MVC.mixin( DatasetCollectionElementMixin,
/** @lends NestedListDCDCE.prototype */{

    /** This is both a collection and a collection element - call the constructor */
    constructor : function( attributes, options ){
        this.debug( '\t NestedListDCDCE.constructor:', attributes, options );
        DatasetCollectionElementMixin.constructor.call( this, attributes, options );
    },

    /** String representation. */
    toString : function(){
        var objStr = ( this.object )?( '' + this.object ):( this.get( 'element_identifier' ) );
        return ([ 'NestedListDCDCE(', objStr, ')' ].join( '' ));
    }
}));


//==============================================================================
/** @class Backbone collection containing list dataset collections. */
var NestedListDCDCECollection = NestedDCDCECollection.extend({

    /** We know this collection is composed of only nested pair collections */
    model: NestedListDCDCE,

    /** String representation. */
    toString : function(){
        return ([ 'NestedListDCDCECollection(', this.length, ')' ].join( '' ));
    }
});


//==============================================================================
/** @class Backbone Model for a DatasetCollection (list) that contains other lists. */
var ListOfListsDatasetCollection = DatasetCollection.extend({

    /** list:paired is the only collection that itself contains collections */
    collectionClass : NestedListDCDCECollection,

    /** String representation. */
    toString : function(){
        return ([ 'ListOfListsDatasetCollection(', this.get( 'name' ), ')' ].join( '' ));
    }
});


//==============================================================================
    return {
        ListDatasetCollection       : ListDatasetCollection,
        PairDatasetCollection       : PairDatasetCollection,
        ListPairedDatasetCollection : ListPairedDatasetCollection,
        ListOfListsDatasetCollection: ListOfListsDatasetCollection
    };
});
