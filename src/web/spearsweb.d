/*
 * Copyright (C) 2017 Matthias Klumpp <matthias@tenstral.net>
 *
 * Licensed under the GNU Lesser General Public License Version 3
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 3 of the license, or
 * (at your option) any later version.
 *
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this software.  If not, see <http://www.gnu.org/licenses/>.
 */

module web.spearsweb;

import std.exception : enforce;
import std.conv : to;
import std.array : empty;
import vibe.core.log;
import vibe.http.router;
import vibe.http.server;
import vibe.utils.validation;
import vibe.web.web;

import laniakea.db;

import web.webconfig;

@path("/migration")
class SpearsWebService {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;
        SessionFactory sFactory;

        SpearsConfigEntry[string] migrationTasks;
        immutable excusesPerPage = 100;
    }

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;

        sFactory = db.newSessionFactory! (SpearsExcuse);

        auto spearsConf = db.getSpearsConfig;
        migrationTasks = spearsConf.migrations;
    }

    @path("/")
 	void getMigrationOverview (HTTPServerRequest req, HTTPServerResponse res)
 	{
        auto migrations = migrationTasks.byValue;
        render!("migration/excuses.dt", ginfo, migrations);
 	}

    @path(":migrationId/excuses/:page")
 	void getMigrationExcuses (HTTPServerRequest req, HTTPServerResponse res)
 	{
        import std.math : ceil;
        import std.range : take;
        immutable migrationId = req.params["migrationId"];

        uint currentPage = 1;
        immutable pageStr = req.params.get("page");
        if (!pageStr.empty) {
            try {
                currentPage = pageStr.to!int;
            } catch (Throwable) {
                return; // not an integer, we can't continue
            }
        }

        logDebug ("Hello! %s", migrationId);
        if (migrationId !in migrationTasks)
            return;
        const migrationDetails = migrationTasks[migrationId];

        auto session = sFactory.openSession ();
        scope (exit) session.close ();
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        auto ps = conn.prepareStatement ("SELECT COUNT(*) FROM spears_excuse;");
        scope (exit) ps.close ();
        Variant v;
        ps.executeUpdate (v);
        const excusesCount = v.get!long;
        immutable pageCount = ceil (excusesCount.to!real / excusesPerPage.to!real);

        auto q = session.createQuery ("FROM SpearsExcuse as e
                                       WHERE migrationId=:mID
                                       ORDER BY sourcePackage")
                        .setParameter("mID", migrationId);

        // FIXME: Hibernated doesn't seem to support LIMIT/OFFSET...
        const excuses = (q.list!SpearsExcuse)[(currentPage - 1) * excusesPerPage .. $].take (excusesPerPage);

        render!("migration/excuses-list.dt", ginfo,
                currentPage, pageCount,
                migrationDetails, excuses);
 	}

    @path(":migrationId/excuses")
 	void getMigrationExcusesPageOne (HTTPServerRequest req, HTTPServerResponse res)
 	{
        res.redirect ("excuses/1");
    }

    @path(":migrationId/excuses/:source/:version")
    void getMigrationExcuseDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        immutable migrationId = req.params["migrationId"];

        immutable sourcePackage = req.params["source"];
        immutable newVersion = req.params["version"];

        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        const excuse = session.createQuery ("FROM SpearsExcuse
                                       WHERE migrationId=:mID
                                         AND sourcePackage=:srcPkgname
                                         AND newVersion=:version")
                              .setParameter("mID", migrationId)
                              .setParameter("srcPkgname", sourcePackage)
                              .setParameter("version", newVersion)
                              .uniqueResult!SpearsExcuse;

        if (excuse is null) {
            res.statusCode = 404;
            res.writeBody("");
            return;
        }

        render!("migration/excuse-details.dt", ginfo, excuse);
    }

}
