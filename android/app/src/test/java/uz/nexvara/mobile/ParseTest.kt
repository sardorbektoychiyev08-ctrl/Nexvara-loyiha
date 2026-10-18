package uz.nexvara.mobile

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Envelopes as the Windows Agent sends them (tests/unit/test_remote_v1_sections.py). */
class ParseTest {
    private val overview = JSONObject("""
        {"pc_name":"ISH-PC","server_id":"0123456789abcdef","app_version":"1.0.1","time":1,
         "tasks":[{"id":"abc123","title":"Excel: jadval","status":"paused","pause_requested":true,
                   "cancel_requested":false,"error":"","created_at":10,"finished_at":null,
                   "steps":[{"name":"Ochish","status":"succeeded","detail":""}],"files":[],"report":[]}],
         "running":1,"counts":{"memory":3,"teach":null,"workflows":2,"dashboards":1},
         "ai":{"enabled":false,"spent_today":0.01,"spent_month":0.2,"daily_budget_usd":1,"monthly_budget_usd":10,
               "warnings":[],"estimated":true,
               "providers":{"openai":{"label":"OpenAI","has_key":true,"spent_today":0.01,"spent_month":0.2,
                    "daily_limit":0.25,"monthly_limit":5,"left_today":0.24,"left_month":4.8,"balance_api":false,
                    "balance":null,"billing_url":"https://platform.openai.com/settings/organization/billing/overview",
                    "usage_url":"https://platform.openai.com/usage","key_url":"","free_tier":""},
                 "deepseek":{"label":"DeepSeek","has_key":true,"spent_today":0,"spent_month":0,"daily_limit":null,
                    "monthly_limit":null,"left_today":null,"left_month":null,"balance_api":true,
                    "balance":{"supported":true,"available":true,"balances":[{"currency":"USD","total":4.5}]},
                    "billing_url":"https://platform.deepseek.com/","usage_url":"","key_url":"","free_tier":""}}},
         "sync":{"available":true,"enabled":true,"folder_name":"NEXVARA-SYNC","google_drive":false,"has_passphrase":true,"last":5},
         "account":{"pc":{"configured":true,"signed_in":true,"owner_set":true,"email":"ega@gmail.com","name":""},
                    "phone":{"web_client_id":"","ready":false,"linked_email":""}}}
    """.trimIndent())

    @Test fun overviewWithPausedTaskAndAiPanel() {
        val o = Parse.overview(overview)
        assertEquals("ISH-PC", o.pcName)
        val t = o.tasks.single()
        assertTrue(t.active && t.pauseRequested)
        assertNull(t.finishedAt)
        assertEquals(3, o.counts["memory"])
        assertNull(o.counts["teach"])
        val oa = o.ai.providers.first { it.id == "openai" }
        assertEquals(0.24, oa.leftToday!!, 1e-9)
        assertNull(oa.balance)
        assertTrue(oa.billingUrl.startsWith("https://"))
        assertEquals("4.50 USD", o.ai.providers.first { it.id == "deepseek" }.balance)
        assertEquals("NEXVARA-SYNC", o.sync.folderName)
        assertEquals("ega@gmail.com", o.account.pcEmail)
        assertFalse(o.account.phoneReady)
    }

    @Test fun biWidgets() {
        val v = Parse.bi(JSONObject("""
            {"name":"Savdo","file":"D:\\NEXVARA\\BI\\savdo.json","page":0,"pages":["Asosiy"],"rows":3,"total_rows":3,"problems":[],
             "widgets":[{"type":"kpi","title":"Jami","value":350.0,"growth":12.5},
                        {"type":"bar","title":"Hudud","labels":["Toshkent","Samarqand"],"values":[150,200]},
                        {"type":"line","title":"Oylar","labels":["2026-01","2026-02"],"series":[{"name":"Summa","values":[100,null]}]},
                        {"type":"table","title":"T","columns":["A","B"],"rows":[["x",1.5],[null,2]]}]}
        """.trimIndent()))
        assertEquals(4, v.widgets.size)
        assertEquals(350.0, v.widgets[0].value!!, 0.0)
        assertEquals(listOf("Toshkent", "Samarqand"), v.widgets[1].labels)
        assertNull(v.widgets[2].series[0].values[1])
        assertEquals(listOf("x", "1.50"), v.widgets[3].rows[0])
        assertEquals(listOf("", "2"), v.widgets[3].rows[1])
    }

    @Test fun libraryCatalogSortedByGrade() {
        val lib = Parse.library(JSONObject("""{"books":[{"label":"Tarix 5","grade":5,"subject":"Tarix","pages":120}],
            "catalog":{"7":["Fizika"],"5":["Tarix","Ona tili"]}}"""))
        assertEquals(listOf(5, 7), lib.catalog.keys.toList())
        assertEquals("Tarix", lib.books.single().subject)
    }

    @Test fun uzbekFormatting() {
        assertEquals("Pauzada", Fmt.status("paused"))
        assertEquals("$0.012", Fmt.usdFine(0.012))
        assertEquals("$4.80", Fmt.usd(4.8))
        assertEquals("—", Fmt.usd(null))
        assertEquals("1.5 mln", Fmt.number(1_500_000.0))
        assertEquals("hali yo‘q", Fmt.ago(0.0))
    }
}
