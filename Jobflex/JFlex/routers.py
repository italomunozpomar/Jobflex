class JFlexRouter:
    """
    A router to control all database operations on models in the
    JFlex application.
    """
    route_app_labels = {'JFlex', 'admin', 'auth', 'contenttypes', 'sessions', 'sites'}

    def db_for_read(self, model, **hints):
        """
        Attempts to read JFlex models go to jflex_db.
        Attempts to read auth and contenttypes models go to default.
        """
        if model._meta.app_label == 'JFlex':
            return 'jflex_db'
        elif model._meta.app_label in self.route_app_labels:
            return 'default'
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write JFlex models go to jflex_db.
        Attempts to write auth and contenttypes models go to default.
        """
        if model._meta.app_label == 'JFlex':
            return 'jflex_db'
        elif model._meta.app_label in self.route_app_labels:
            return 'default'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if both objects are in the same database,
        or if a JFlex model is relating to an auth model.
        """
        if obj1._meta.app_label == 'JFlex' or obj2._meta.app_label == 'JFlex':
            if obj1._meta.app_label in self.route_app_labels and obj2._meta.app_label in self.route_app_labels:
                return True
            return None
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the JFlex app only appears in the 'jflex_db' database.
        The auth and contenttypes apps only appear in the 'default' database.
        """
        if app_label == 'JFlex':
            return db == 'jflex_db'
        elif app_label in self.route_app_labels:
            return db == 'default'
        return None
